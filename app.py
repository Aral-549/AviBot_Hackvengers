"""
Social Saver Bot - Main Application
Flask web app with WhatsApp webhook integration
"""

import os
import re
import threading
from flask import Flask, render_template, request, jsonify, redirect, url_for, make_response
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from config import Config, get_config, is_valid_url, detect_platform
from database import (
    init_db, save_content, get_all_content, get_content_by_id,
    get_categories, get_platforms, get_stats, get_random_content,
    search_content, delete_content, update_content, check_duplicate,
    get_random_content_by_category, get_related_content,
    get_content_count_by_category, get_total_content_count, get_streak_stats,
    get_collections, create_collection, assign_collection, delete_collection,
    get_daily_save_counts
)
from content_extractor import extract_content
from ai_processor import process_content, ai_processor

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY

# Initialize database
init_db()


# ==================== Dashboard Routes ====================

@app.route('/favicon.ico')
def favicon():
    """Serve favicon - returns empty response"""
    response = make_response('', 204)
    return response


@app.route('/')
def index():
    """Main dashboard page"""
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
def dashboard():
    """Dashboard with all saved content"""
    page = request.args.get('page', 1, type=int)
    platform = request.args.get('platform', '')
    category = request.args.get('category', '')
    # Read the search query and pass it to template
    search_query = request.args.get('q', '').strip()

    limit = Config.ITEMS_PER_PAGE
    offset = (page - 1) * limit

    # If search query exists, use search_content instead of get_all_content
    if search_query:
        content = search_content(search_query, limit=limit)
    else:
        content = get_all_content(
            limit=limit,
            offset=offset,
            platform=platform if platform else None,
            category=category if category else None
        )

    stats = get_stats()
    categories = get_categories()
    platforms = get_platforms()

    total_pages = (stats['total'] + limit - 1) // limit

    response = make_response(render_template(
        'dashboard.html',
        content=content,
        stats=stats,
        categories=categories,
        platforms=platforms,
        current_page=page,
        total_pages=total_pages,
        selected_platform=platform,
        selected_category=category,
        search_query=search_query,
        collections=get_collections(),
        selected_collection=''
    ))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/content/<int:content_id>')
def content_detail(content_id):
    """View single content detail"""
    content = get_content_by_id(content_id)
    if not content:
        return "Content not found", 404
    return render_template('content.html', content=content, collections=get_collections())


@app.route('/search')
def search():
    """Search content (legacy route - redirects to dashboard with q param)"""
    query = request.args.get('q', '')
    if not query:
        return redirect(url_for('dashboard'))
    return redirect(url_for('dashboard', q=query))


@app.route('/stats')
def stats_page():
    """Statistics page"""
    import json
    stats = get_stats()
    categories = get_categories()
    platforms = get_platforms()
    heatmap_data = get_daily_save_counts(365)

    return render_template(
        'stats.html',
        stats=stats,
        categories=categories,
        platforms=platforms,
        heatmap_data=json.dumps(heatmap_data),
        recent=get_all_content(limit=8),
        collections=get_collections()
    )


@app.route('/discover')
def discover():
    """Discover random content"""
    page = request.args.get('page', 1, type=int)
    platform = request.args.get('platform', '')
    category = request.args.get('category', '')
    search_query = request.args.get('q', '').strip()
    
    limit = Config.ITEMS_PER_PAGE
    offset = (page - 1) * limit
    
    if search_query:
        content = search_content(search_query, limit=limit)
    else:
        content = get_all_content(
            limit=limit,
            offset=offset,
            platform=platform if platform else None,
            category=category if category else None
        )
    
    stats = get_stats()
    categories = get_categories()
    platforms = get_platforms()
    
    total_pages = (stats['total'] + limit - 1) // limit
    
    return render_template(
        'discover.html',
        content=content,
        stats=stats,
        categories=categories,
        platforms=platforms,
        current_page=page,
        total_pages=total_pages,
        selected_platform=platform,
        selected_category=category,
        search_query=search_query,
        collections=get_collections()
    )


# ==================== API Routes ====================

@app.route('/api/content', methods=['GET'])
def api_get_content():
    """API: Get all content with filters"""
    page = request.args.get('page', 1, type=int)
    platform = request.args.get('platform', '')
    category = request.args.get('category', '')

    limit = request.args.get('limit', Config.ITEMS_PER_PAGE, type=int)
    offset = (page - 1) * limit

    content = get_all_content(
        limit=limit,
        offset=offset,
        platform=platform if platform else None,
        category=category if category else None
    )

    return jsonify({
        'success': True,
        'data': content,
        'page': page,
        'limit': limit
    })


@app.route('/api/content', methods=['POST'])
def api_save_content():
    """API: Save new content"""
    data = request.get_json()

    if not data or 'url' not in data:
        return jsonify({'success': False, 'error': 'URL is required'}), 400

    url = data['url']

    if not is_valid_url(url):
        return jsonify({'success': False, 'error': 'Invalid URL'}), 400

    # Extract content
    extracted = extract_content(url)

    if not extracted.get('success'):
        return jsonify({'success': False, 'error': extracted.get('error', 'Failed to extract content')}), 400

    title = extracted.get('title', '')
    caption = extracted.get('caption', '')
    platform = extracted.get('platform', detect_platform(url))
    image_url = extracted.get('image_url', '')
    media_url = extracted.get('media_url', '')
    media_type = extracted.get('media_type', '')
    media_extraction_status = extracted.get('media_extraction_status', '')
    media_extraction_error = extracted.get('media_extraction_error', '')

    ai_result = {}
    if ai_processor.is_configured():
        try:
            ai_result = process_content(url, title, caption, platform, media_url, media_type, image_url)
        except Exception as e:
            print(f"AI processing error: {e}")
            ai_result = {'category': 'Other', 'summary': '', 'summary_source': '', 'video_summary': '', 'video_summary_status': '', 'tags': ''}
    else:
        ai_result = {'category': 'Other', 'summary': '', 'summary_source': '', 'video_summary': '', 'video_summary_status': '', 'tags': ''}

    content_id = save_content(
        url=url,
        platform=platform,
        title=title,
        caption=caption,
        image_url=image_url,
        media_extraction_status=media_extraction_status,
        media_extraction_error=media_extraction_error,
        category=ai_result.get('category', 'Other'),
        summary=ai_result.get('summary', ''),
        summary_source=ai_result.get('summary_source', ''),
        video_summary=ai_result.get('video_summary', ''),
        video_summary_status=ai_result.get('video_summary_status', ''),
        tags=ai_result.get('tags', ''),
        user_phone=data.get('user_phone')
    )
    content = get_content_by_id(content_id)
    if not content:
        return jsonify({'success': False, 'error': 'Content not found'}), 404
    return jsonify({'success': True, 'data': content})


@app.route('/api/content/<int:content_id>', methods=['GET'])
def api_get_content_by_id(content_id):
    """API: Get one content item for editing."""
    content = get_content_by_id(content_id)
    if not content:
        return jsonify({'success': False, 'error': 'Content not found'}), 404
    return jsonify({'success': True, 'data': content})


@app.route('/api/content/<int:content_id>', methods=['PUT'])
def api_update_content(content_id):
    """API: Update content"""
    data = request.get_json()

    success = update_content(
        content_id=content_id,
        title=data.get('title'),
        caption=data.get('caption'),
        category=data.get('category'),
        summary=data.get('summary'),
        tags=data.get('tags')
    )

    return jsonify({'success': success})


@app.route('/api/content/<int:content_id>/regenerate', methods=['POST'])
def api_regenerate_ai(content_id):
    """API: Regenerate AI content (category, summary, tags) for existing item"""
    content = get_content_by_id(content_id)
    if not content:
        return jsonify({'success': False, 'error': 'Content not found'}), 404

    print(f"\n=== Regenerating AI for content ID {content_id} ===")

    title = content['title']
    caption = content['caption']
    platform = content['platform']
    image_url = content.get('image_url', '')
    media_extraction_status = content.get('media_extraction_status', '')
    media_extraction_error = content.get('media_extraction_error', '')

    ai_result = {}
    if ai_processor.is_configured():
        try:
            refreshed = extract_content(content['url'])
            title = refreshed.get('title', content['title']) if refreshed.get('success') else content['title']
            caption = refreshed.get('caption', content['caption']) if refreshed.get('success') else content['caption']
            platform = refreshed.get('platform', content['platform']) if refreshed.get('success') else content['platform']
            image_url = refreshed.get('image_url', content.get('image_url', '')) if refreshed.get('success') else content.get('image_url', '')
            media_url = refreshed.get('media_url', '') if refreshed.get('success') else ''
            media_type = refreshed.get('media_type', '') if refreshed.get('success') else ''
            media_extraction_status = refreshed.get('media_extraction_status', content.get('media_extraction_status', '')) if refreshed.get('success') else content.get('media_extraction_status', '')
            media_extraction_error = refreshed.get('media_extraction_error', content.get('media_extraction_error', '')) if refreshed.get('success') else content.get('media_extraction_error', '')

            ai_result = process_content(
                content['url'],
                title,
                caption,
                platform,
                media_url,
                media_type,
                image_url
            )
            print(f"AI Result: {ai_result}")
        except Exception as e:
            print(f"AI regeneration error: {e}")
            ai_result = {
                'category': 'Other',
                'summary': f'Error generating: {str(e)}',
                'summary_source': 'error',
                'video_summary': '',
                'video_summary_status': 'video_analysis_failed',
                'tags': ''
            }
    else:
        print("AI processor not configured!")
        ai_result = {
            'category': 'Other',
            'summary': 'AI not configured',
            'summary_source': 'disabled',
            'video_summary': '',
            'video_summary_status': 'gemini_disabled',
            'tags': ''
        }

    success = update_content(
        content_id=content_id,
        title=title,
        caption=caption,
        image_url=image_url,
        media_extraction_status=media_extraction_status,
        media_extraction_error=media_extraction_error,
        category=ai_result.get('category', 'Other'),
        summary=ai_result.get('summary', ''),
        summary_source=ai_result.get('summary_source', ''),
        video_summary=ai_result.get('video_summary', ''),
        video_summary_status=ai_result.get('video_summary_status', ''),
        tags=ai_result.get('tags', '')
    )
    print(f"Update success: {success}")

    ai_result['media_extraction_status'] = media_extraction_status
    ai_result['media_extraction_error'] = media_extraction_error

    return jsonify({'success': success, 'data': ai_result})


@app.route('/api/content/<int:content_id>/video-summary', methods=['POST'])
def api_regenerate_video_summary(content_id):
    """API: Regenerate only the video summary for an existing item"""
    content = get_content_by_id(content_id)
    if not content:
        return jsonify({'success': False, 'error': 'Content not found'}), 404
        
    print(f"\n=== Regenerating Video Summary for content ID {content_id} ===")
    
    video_summary = ''
    video_summary_status = ''
    media_extraction_status = content.get('media_extraction_status', '')
    media_extraction_error = content.get('media_extraction_error', '')
    if ai_processor.is_configured():
        try:
            refreshed = extract_content(content['url'])
            media_url = refreshed.get('media_url', '') if refreshed.get('success') else ''
            media_type = refreshed.get('media_type', '') if refreshed.get('success') else ''
            media_extraction_status = refreshed.get('media_extraction_status', content.get('media_extraction_status', '')) if refreshed.get('success') else content.get('media_extraction_status', '')
            media_extraction_error = refreshed.get('media_extraction_error', content.get('media_extraction_error', '')) if refreshed.get('success') else content.get('media_extraction_error', '')
            
            video_summary, video_summary_status = ai_processor.generate_video_summary(
                url=content['url'],
                title=content['title'],
                caption=content['caption'],
                platform=content['platform'],
                media_url=media_url,
                media_type=media_type
            )
            print("Video summary generated.")
        except Exception as e:
            print(f"Video summary error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
            
    # Update only the video summary
    success = update_content(
        content_id=content_id,
        title=content['title'],
        caption=content['caption'],
        image_url=content.get('image_url', ''),
        media_extraction_status=media_extraction_status,
        media_extraction_error=media_extraction_error,
        category=content['category'],
        summary=content.get('summary', ''),
        summary_source=content.get('summary_source', ''),
        video_summary=video_summary,
        video_summary_status=video_summary_status,
        tags=content.get('tags', '')
    )
    
    return jsonify({
        'success': success,
        'video_summary': video_summary,
        'video_summary_status': video_summary_status,
        'media_extraction_status': media_extraction_status,
        'media_extraction_error': media_extraction_error
    })



@app.route('/api/content/<int:content_id>', methods=['DELETE'])
def api_delete_content(content_id):
    """API: Delete content"""
    success = delete_content(content_id)
    return jsonify({'success': success})


@app.route('/api/stats', methods=['GET'])
def api_get_stats():
    """API: Get statistics"""
    stats = get_stats()
    return jsonify({'success': True, 'data': stats})


@app.route('/api/random', methods=['GET'])
def api_get_random():
    """API: Get random content item"""
    exclude_id = request.args.get('exclude', type=int)
    items = get_random_content(1, exclude_id=exclude_id)
    if items:
        item = items[0]
        return jsonify({
            'success': True,
            'data': {
                'id': item['id'],
                'title': item['title'],
                'platform': item['platform'],
                'category': item['category'],
                'summary': item['summary'],
                'url': item['url'],
                'thumbnail_url': item.get('image_url', ''),
                'tags': item.get('tags', ''),
                'caption': item.get('caption', '')
            }
        })
    return jsonify({'success': False, 'error': 'No content found'}), 404


@app.route('/api/categories', methods=['GET'])
def api_get_categories():
    """API: Get all categories"""
    categories = get_categories()
    return jsonify({'success': True, 'data': categories})


# ==================== WhatsApp Webhook Routes ====================

def send_whatsapp_message(to_phone: str, body: str) -> bool:
    """Send a WhatsApp message using the Twilio REST API."""
    if not (Config.TWILIO_ACCOUNT_SID and Config.TWILIO_AUTH_TOKEN and Config.TWILIO_PHONE_NUMBER):
        print("WhatsApp send skipped: Twilio is not fully configured.")
        return False

    try:
        destination = to_phone if to_phone.startswith('whatsapp:') else f'whatsapp:{to_phone}'
        client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=body,
            from_=f"whatsapp:{Config.TWILIO_PHONE_NUMBER}",
            to=destination
        )
        return True
    except Exception as exc:
        print(f"WhatsApp send error: {exc}")
        return False


def process_whatsapp_url(url: str, from_phone: str, base_url: str) -> None:
    """Process a WhatsApp URL in the background and send the final result separately."""
    try:
        existing = check_duplicate(url)
        if existing:
            message = f"You already saved this on {existing['timestamp']}!\n\n"
            message += f"Title: {existing['title']}\n"
            message += f"Category: {existing['category']}\n"
            message += f"Summary: {existing['summary']}\n\n"
            message += f"View it: {base_url}/content/{existing['id']}"
            send_whatsapp_message(from_phone, message)
            return

        extracted = extract_content(url)
        if not extracted.get('success'):
            send_whatsapp_message(
                from_phone,
                f"Failed to extract content: {extracted.get('error', 'Unknown error')}"
            )
            return

        title = extracted.get('title', '')
        caption = extracted.get('caption', '')
        platform = extracted.get('platform', detect_platform(url))
        image_url = extracted.get('image_url', '')
        media_url = extracted.get('media_url', '')
        media_type = extracted.get('media_type', '')
        media_extraction_status = extracted.get('media_extraction_status', '')
        media_extraction_error = extracted.get('media_extraction_error', '')

        if ai_processor.is_configured():
            ai_result = process_content(url, title, caption, platform, media_url, media_type, image_url)
        else:
            ai_result = {
                'category': 'Other',
                'summary': '',
                'summary_source': '',
                'video_summary': '',
                'video_summary_status': '',
                'tags': ''
            }

        category = ai_result.get('category', 'Other')
        content_id = save_content(
            url=url,
            platform=platform,
            title=title,
            caption=caption,
            image_url=image_url,
            media_extraction_status=media_extraction_status,
            media_extraction_error=media_extraction_error,
            category=category,
            summary=ai_result.get('summary', ''),
            summary_source=ai_result.get('summary_source', ''),
            video_summary=ai_result.get('video_summary', ''),
            video_summary_status=ai_result.get('video_summary_status', ''),
            tags=ai_result.get('tags', ''),
            user_phone=from_phone
        )

        message = "Content saved successfully!\n\n"
        message += f"Title: {title[:50]}{'...' if len(title) > 50 else ''}\n"
        message += f"Platform: {platform}\n"
        message += f"Category: {category}\n"

        if ai_result.get('video_summary'):
            message += "Video summary: available\n"
        elif ai_result.get('video_summary_status'):
            message += f"Video summary: {ai_result['video_summary_status'].replace('_', ' ')}\n"
            if ai_result.get('video_summary_status') == 'video_media_missing' and media_extraction_status:
                message += f"Extraction: {media_extraction_status.replace('_', ' ')}\n"

        if ai_result.get('summary'):
            message += f"Summary: {ai_result['summary']}\n"

        message += f"\nView on dashboard: {base_url}/content/{content_id}"
        send_whatsapp_message(from_phone, message)
    except Exception as exc:
        print(f"Error processing WhatsApp message: {exc}")
        send_whatsapp_message(
            from_phone,
            "An error occurred while processing your URL. Please try again."
        )


def start_whatsapp_url_processing(url: str, from_phone: str, base_url: str) -> None:
    """Start asynchronous WhatsApp URL processing."""
    worker = threading.Thread(
        target=process_whatsapp_url,
        args=(url, from_phone, base_url),
        daemon=True
    )
    worker.start()

@app.route('/whatsapp/webhook', methods=['GET'])
def whatsapp_verify():
    """WhatsApp webhook verification"""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    if mode == 'subscribe' and token == Config.WHATSAPP_WEBHOOK_VERIFY_TOKEN:
        return challenge, 200
    return 'Verification failed', 403


@app.route('/whatsapp/webhook', methods=['POST'])
def whatsapp_webhook():
    """WhatsApp webhook (POST) - Handle incoming messages"""
    from_xml = request.values.get('Body', '')
    from_phone = request.values.get('From', '')
    message_text = from_xml.strip().lower()
    url_match = re.search(r'https?://[^\s]+', from_xml)

    response = MessagingResponse()

    if url_match:
        url = url_match.group(0)

        if not is_valid_url(url):
            response.message("Invalid URL. Please send a valid URL to save.")
            return str(response)

        existing = check_duplicate(url)
        if existing:
            base_url = request.host_url.rstrip('/')
            message = f"You already saved this on {existing['timestamp']}!\n\n"
            message += f"Title: {existing['title']}\n"
            message += f"Category: {existing['category']}\n"
            message += f"Summary: {existing['summary']}\n\n"
            message += f"View it: {base_url}/content/{existing['id']}"
            response.message(message)
            return str(response)

        start_whatsapp_url_processing(url, from_phone, request.host_url.rstrip('/'))
        response.message("Processing your URL now. I'll send the result shortly.")
        return str(response)

    else:
        # Handle text commands
        if message_text in ['surprise me', 'inspire me']:
            items = get_random_content(1)
            if items:
                item = items[0]
                message = f"Here's something from your saves:\n\n"
                message += f"Title: {item['title']}\n"
                message += f"Category: {item['category']}\n"
                message += f"Summary: {item['summary']}\n\n"
                message += f"URL: {item['url']}"
            else:
                message = "You don't have any saved content yet! Send me a URL to get started."
            response.message(message)

        elif message_text == 'motivate me':
            categories = ['Motivation & Self-Help', 'Fitness & Workouts', 'Mental Health & Mindfulness']
            items = get_random_content_by_category(1, categories) or get_random_content(1)
            if items:
                item = items[0]
                message = f"Here's something from your saves:\n\n"
                message += f"Title: {item['title']}\n"
                message += f"Category: {item['category']}\n"
                message += f"Summary: {item['summary']}\n\n"
                message += f"URL: {item['url']}"
            else:
                message = "You don't have any saved content yet! Send me a URL to get started."
            response.message(message)

        elif message_text == 'teach me':
            categories = ['Programming & Coding', 'Education', 'Science & Research', 'Data Science']
            items = get_random_content_by_category(1, categories) or get_random_content(1)
            if items:
                item = items[0]
                message = f"Here's something from your saves:\n\n"
                message += f"Title: {item['title']}\n"
                message += f"Category: {item['category']}\n"
                message += f"Summary: {item['summary']}\n\n"
                message += f"URL: {item['url']}"
            else:
                message = "You don't have any saved content yet! Send me a URL to get started."
            response.message(message)

        elif message_text == 'feed me':
            categories = ['Recipes & Cooking', 'Food Science']
            items = get_random_content_by_category(1, categories) or get_random_content(1)
            if items:
                item = items[0]
                message = f"Here's something from your saves:\n\n"
                message += f"Title: {item['title']}\n"
                message += f"Category: {item['category']}\n"
                message += f"Summary: {item['summary']}\n\n"
                message += f"URL: {item['url']}"
            else:
                message = "You don't have any saved content yet! Send me a URL to get started."
            response.message(message)

        elif message_text in ['my streak', 'stats']:
            streak_data = get_streak_stats(from_phone)
            current = streak_data['current_streak']
            weekly = streak_data['total_this_week']
            best = streak_data['best_streak']

            if current == 0:
                motivational = "Start saving today to begin your streak!"
            elif current <= 3:
                motivational = "Great start! Keep it going!"
            elif current <= 6:
                motivational = "You're on fire! Don't break the chain!"
            else:
                motivational = "Legendary! You're a knowledge hoarder!"

            message = f"Your Social Saver Stats!\n\n"
            message += f"Current streak: {current} days\n"
            message += f"Saved this week: {weekly} links\n"
            message += f"Best streak ever: {best} days\n\n"
            message += motivational
            response.message(message)

        elif message_text.startswith('ask:'):
            question = from_xml.strip()[4:].strip()  # preserve original casing for the question
            if not question:
                response.message("Please include a question after 'ask:'\n\nExample: ask: what did I save about Python?")
            else:
                # Search saved content for relevant items to use as RAG context
                results = search_content(question, limit=5)
                if not results:
                    response.message("I couldn't find anything relevant in your saves. Try saving some content on this topic first!")
                else:
                    context_lines = []
                    for item in results:
                        context_lines.append(
                            f"Title: {item.get('title', 'Untitled')}\n"
                            f"Summary: {item.get('summary', '')}\n"
                            f"Category: {item.get('category', '')}\n"
                            f"Tags: {item.get('tags', '')}\n"
                            f"URL: {item.get('url', '')}"
                        )
                    context = "\n\n---\n\n".join(context_lines)

                    if ai_processor.is_configured():
                        from ai_processor import rag_answer
                        answer = rag_answer(question, context)
                    else:
                        # Fallback: just list the top matching saves without AI
                        answer = f"Found {len(results)} relevant save(s):\n\n"
                        for item in results:
                            answer += f"- {item.get('title', 'Untitled')}: {item.get('url', '')}\n"

                    response.message(answer)

        else:
            response.message("Welcome to Social Saver Bot!\n\n"
                            "Send me any URL from Instagram, Twitter, Facebook, YouTube, "
                            "or any blog, and I'll save it with AI-generated categories and summaries.\n\n"
                            "Or try these commands:\n"
                            "- 'surprise me' - Random pick\n"
                            "- 'motivate me' - Motivation & wellness\n"
                            "- 'teach me' - Learning & tech\n"
                            "- 'feed me' - Food & recipes\n"
                            "- 'my streak' - Your saving streak\n"
                            "- 'ask: <question>' - Search your saves with AI\n\n"
                            f"View your saved content: {request.host_url}dashboard")

    return str(response)


# ==================== Utility Routes ====================

def get_time_ago(timestamp_str: str) -> str:
    """Calculate human-readable time ago from timestamp string"""
    from datetime import datetime
    try:
        saved_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        now = datetime.now()
        diff = now - saved_time
        days = diff.days
        weeks = days // 7
        months = days // 30

        if days == 0:
            return "today"
        elif days == 1:
            return "1 day ago"
        elif days < 7:
            return f"{days} days ago"
        elif weeks == 1:
            return "1 week ago"
        elif weeks < 4:
            return f"{weeks} weeks ago"
        elif months == 1:
            return "1 month ago"
        else:
            return f"{months} months ago"
    except Exception:
        return "a while ago"


@app.route('/send-daily-dose', methods=['GET'])
def send_daily_dose():
    """Send daily dose of inspiration via WhatsApp"""
    try:
        items = get_random_content(1)
        if not items:
            return "No content saved yet", 200

        item = items[0]
        time_ago = get_time_ago(item['timestamp'])

        message = f"Your Daily Dose of Inspiration!\n\n"
        message += f"You saved this {time_ago} and never revisited it\n\n"
        message += f"Title: {item['title']}\n"
        message += f"Category: {item['category']}\n"
        message += f"Summary: {item['summary']}\n\n"
        message += f"URL: {item['url']}\n\n"
        message += f"Rediscover something great today!"

        if Config.TWILIO_ACCOUNT_SID and Config.TWILIO_AUTH_TOKEN and Config.TWILIO_PHONE_NUMBER:
            client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=message,
                from_=f"whatsapp:{Config.TWILIO_PHONE_NUMBER}",
                to=f"whatsapp:{Config.TWILIO_PHONE_NUMBER}"
            )
            return f"Daily dose sent!\n\n{message}", 200
        else:
            return f"Twilio not configured. Message would be:\n\n{message}", 200

    except Exception as e:
        print(f"Error sending daily dose: {e}")
        return f"Error: {str(e)}", 500


@app.route('/schedule-daily-dose', methods=['GET'])
def schedule_daily_dose():
    """Start background scheduler for daily dose at 8:00 AM"""
    try:
        import schedule
        import time
        import threading

        def run_scheduler():
            schedule.every().day.at("08:00").do(send_daily_dose)
            while True:
                schedule.run_pending()
                time.sleep(60)

        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()

        return "Daily dose scheduler started! Will send at 8:00 AM daily.", 200
    except Exception as e:
        return f"Error: {str(e)}", 500


@app.route('/send-weekly-digest', methods=['GET'])
def send_weekly_digest():
    """Send weekly digest via WhatsApp"""
    try:
        total = get_total_content_count(7)
        category_counts = get_content_count_by_category(7)

        if total == 0:
            return "No content saved in the last 7 days", 200

        sorted_cats = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
        top_3 = sorted_cats[:3]

        base_url = request.host_url.rstrip('/')
        message = f"Your Weekly Social Saver Digest!\n\n"
        message += f"You saved {total} links this week\n\n"
        message += "Top categories:\n"

        medals = ['1st', '2nd', '3rd']
        for i, (cat, count) in enumerate(top_3):
            message += f"{medals[i]} {cat} - {count} links\n"

        message += "\nKeep it up!\n"
        message += f"View dashboard: {base_url}/dashboard"

        if Config.TWILIO_ACCOUNT_SID and Config.TWILIO_AUTH_TOKEN and Config.TWILIO_PHONE_NUMBER:
            client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=message,
                from_=f"whatsapp:{Config.TWILIO_PHONE_NUMBER}",
                to=f"whatsapp:{Config.TWILIO_PHONE_NUMBER}"
            )
            return f"Digest sent!\n\n{message}", 200
        else:
            return f"Twilio not configured. Message would be:\n\n{message}", 200

    except Exception as e:
        print(f"Error sending digest: {e}")
        return f"Error: {str(e)}", 500


# ==================== CSV Export ====================

@app.route('/export/csv')
def export_csv():
    """Export all content as CSV"""
    import csv
    import io
    from flask import Response
    
    items = get_all_content(limit=10000)
    output = io.StringIO()
    fields = [
        'id', 'url', 'platform', 'title', 'caption', 'image_url',
        'media_extraction_status', 'media_extraction_error',
        'category', 'summary', 'summary_source',
        'video_summary', 'video_summary_status', 'tags', 'timestamp'
    ]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction='ignore')
    writer.writeheader()
    for item in items:
        writer.writerow({k: item.get(k, '') for k in fields})
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=social_saver_export.csv'}
    )


# ==================== Collections ====================

@app.route('/collections')
def collections_page():
    """Collections/ folders page - dedicated page"""
    collections = get_collections()
    selected = request.args.get('collection', '')
    all_items = get_all_content(limit=500)
    
    if selected:
        filtered = [i for i in all_items if i.get('collection') == selected]
    else:
        filtered = all_items

    return render_template('collections.html',
        collections=collections,
        selected_collection=selected,
        content_list=filtered,
        all_items=all_items,
        stats=get_stats(),
    )


@app.route('/collections/create', methods=['POST'])
def create_collection_route():
    """Create a new collection"""
    name = request.form.get('name', '').strip()
    if name:
        create_collection(name)
    return redirect('/collections')


@app.route('/collections/assign', methods=['POST'])
def assign_collection_route():
    """Assign content to a collection"""
    content_id = request.form.get('content_id')
    collection = request.form.get('collection', '')
    if content_id:
        assign_collection(int(content_id), collection)
    return jsonify({'success': True})


@app.route('/collections/delete', methods=['POST'])
def delete_collection_route():
    """Delete a collection"""
    from database import delete_collection
    name = request.form.get('name', '').strip()
    if name:
        delete_collection(name)
    return redirect('/collections')


# ==================== Error Handlers ====================

@app.errorhandler(404)
def not_found(e):
    return f"""
    <html><body style="background:#0f172a;color:#f8fafc;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;flex-direction:column;gap:1rem">
    <h1 style="font-size:4rem;margin:0">404</h1>
    <p style="color:#94a3b8">Page not found</p>
    <a href="/" style="color:#6366f1">Back to Dashboard</a>
    </body></html>
    """, 404


@app.errorhandler(500)
def server_error(e):
    return f"""
    <html><body style="background:#0f172a;color:#f8fafc;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;flex-direction:column;gap:1rem">
    <h1 style="font-size:4rem;margin:0">500</h1>
    <p style="color:#94a3b8">Something went wrong on our end</p>
    <a href="/" style="color:#6366f1">Back to Dashboard</a>
    </body></html>
    """, 500


@app.route('/export/obsidian')
@app.route('/export/zip')
def export_obsidian_zip():
    """Export all saved bookmarks as an Obsidian Note Vault zip archive."""
    import zipfile
    import io
    from flask import Response
    from database import OBSIDIAN_VAULT_DIR, export_to_obsidian_note

    items = get_all_content(limit=10000)
    for item in items:
        export_to_obsidian_note(item)

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(OBSIDIAN_VAULT_DIR):
            for filename in os.listdir(OBSIDIAN_VAULT_DIR):
                if filename.endswith('.md'):
                    filepath = os.path.join(OBSIDIAN_VAULT_DIR, filename)
                    zf.write(filepath, arcname=f"Obsidian_Vault/{filename}")

    memory_file.seek(0)
    return Response(
        memory_file.getvalue(),
        mimetype='application/zip',
        headers={'Content-Disposition': 'attachment; filename=AVI_Bot_Obsidian_Vault.zip'}
    )


# ==================== Main Entry Point ====================

if __name__ == '__main__':
    config = get_config()
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG
    )
