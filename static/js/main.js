/**
 * AVI Bot frontend interactions.
 */

/* Close nav dropdowns on outside click */
document.addEventListener('click', function(e) {
    document.querySelectorAll('.nav-dropdown.open').forEach(function(dd) {
        if (!dd.contains(e.target)) dd.classList.remove('open');
    });
});

function showToast(message, type = 'success') {
    const container = document.getElementById('toast');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast-item ${type}`;
    const icon = type === 'success' ? 'check-circle' : 'exclamation-circle';
    toast.innerHTML = `<i class="fas fa-${icon}"></i> ${message}`;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3200);
}

function safeString(value) {
    if (value === null || value === undefined) return '';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
}

function checkImg(img) {
    setTimeout(() => {
        if (img.naturalWidth <= 120 && img.naturalHeight <= 90) swapPh(img);
    }, 50);
}

function swapPh(img) {
    img.style.display = 'none';
    const placeholder = img.nextElementSibling;
    if (placeholder && placeholder.classList.contains('card-placeholder')) {
        placeholder.style.display = 'flex';
    }
}

function filterAll() {
    window.location.href = window.discoverUrl || '/discover';
}

function filterPlatform(platform) {
    window.location.href = `${window.discoverUrl || '/discover'}?platform=${encodeURIComponent(platform)}`;
}

async function copyLink(url, btn) {
    try {
        await navigator.clipboard.writeText(url);
        const icon = btn?.querySelector('i');
        if (icon) icon.className = 'fas fa-check';
        showToast('Link copied', 'success');
        setTimeout(() => {
            if (icon) icon.className = 'fas fa-link';
        }, 1400);
    } catch (err) {
        showToast('Could not copy link', 'error');
    }
}

document.getElementById('addContentForm')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const input = document.getElementById('contentUrl');
    const url = input?.value.trim();
    const button = event.target.querySelector('button');
    const originalText = button?.innerHTML;

    if (!url) {
        showToast('Paste a URL first', 'error');
        return;
    }

    if (button) {
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
    }

    try {
        const response = await fetch('/api/content', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });
        const data = await response.json();

        if (data.success) {
            showToast('Content saved', 'success');
            if (input) input.value = '';
            setTimeout(() => location.reload(), 800);
        } else {
            showToast(data.error || 'Failed to save content', 'error');
        }
    } catch (err) {
        showToast('Network error while saving', 'error');
    } finally {
        if (button) {
            button.disabled = false;
            button.innerHTML = originalText;
        }
    }
});

async function deleteContent(id) {
    if (!confirm('Delete this saved item?')) return;

    try {
        const response = await fetch(`/api/content/${id}`, { method: 'DELETE' });
        const data = await response.json();

        if (data.success) {
            showToast('Content deleted', 'success');
            const card = document.getElementById(`card-${id}`);
            if (card) {
                card.style.transition = 'opacity 220ms ease, transform 220ms ease';
                card.style.opacity = '0';
                card.style.transform = 'scale(0.98)';
                setTimeout(() => card.remove(), 230);
            }
        } else {
            showToast('Failed to delete content', 'error');
        }
    } catch (err) {
        showToast('Network error while deleting', 'error');
    }
}

async function regenerateAI(id) {
    if (!confirm('Regenerate the AI summary, category, and tags for this item?')) return;

    const button = document.querySelector(`button[onclick*="regenerateAI(${id})"]`);
    const originalText = button?.innerHTML;
    if (button) {
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    }

    try {
        const response = await fetch(`/api/content/${id}/regenerate`, { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            showToast('AI content regenerated', 'success');
            setTimeout(() => location.reload(), 600);
        } else {
            showToast(data.error || 'Failed to regenerate AI content', 'error');
        }
    } catch (err) {
        showToast('Network error while regenerating', 'error');
    } finally {
        if (button) {
            button.disabled = false;
            button.innerHTML = originalText;
        }
    }
}

async function editContent(id) {
    try {
        const response = await fetch(`/api/content/${id}`);
        const data = await response.json();

        if (!data.success) {
            showToast(data.error || 'Failed to load content', 'error');
            return;
        }

        const content = data.data;
        document.getElementById('editId').value = content.id;
        document.getElementById('editTitle').value = safeString(content.title);
        document.getElementById('editCaption').value = safeString(content.caption) || safeString(content.summary);
        document.getElementById('editCategory').value = safeString(content.category) || 'Other';
        document.getElementById('editTags').value = safeString(content.tags);
        document.getElementById('editModal')?.classList.add('active');
    } catch (err) {
        showToast('Network error while loading content', 'error');
    }
}

function closeModal() {
    document.getElementById('editModal')?.classList.remove('active');
}

document.getElementById('editModal')?.addEventListener('click', (event) => {
    if (event.target.id === 'editModal') closeModal();
});

document.getElementById('editForm')?.addEventListener('submit', async (event) => {
    event.preventDefault();

    const id = document.getElementById('editId').value;
    const data = {
        title: document.getElementById('editTitle').value,
        caption: document.getElementById('editCaption').value,
        category: document.getElementById('editCategory').value,
        tags: document.getElementById('editTags').value
    };

    try {
        const response = await fetch(`/api/content/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const result = await response.json();

        if (result.success) {
            showToast('Content updated', 'success');
            closeModal();
            setTimeout(() => location.reload(), 500);
        } else {
            showToast('Failed to update content', 'error');
        }
    } catch (err) {
        showToast('Network error while updating', 'error');
    }
});

async function assignToFolder(id, selectEl) {
    const value = selectEl.value;
    const form = new FormData();
    form.append('content_id', id);
    form.append('collection', value);

    try {
        const response = await fetch('/collections/assign', { method: 'POST', body: form });
        const data = await response.json();
        if (data.success) {
            showToast(value ? `Added to ${value}` : 'Removed from collection', 'success');
            setTimeout(() => location.reload(), 700);
        } else {
            showToast('Failed to update collection', 'error');
        }
    } catch (err) {
        showToast('Network error while updating collection', 'error');
    }
}

document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeModal();
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'n') {
        const input = document.getElementById('contentUrl');
        if (input) {
            event.preventDefault();
            input.focus();
        }
    }
});

document.addEventListener('DOMContentLoaded', () => {
    const revealItems = document.querySelectorAll('.reveal');
    if (!('IntersectionObserver' in window)) {
        revealItems.forEach((item) => item.classList.add('is-visible'));
        return;
    }

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.12 });

    revealItems.forEach((item, index) => {
        if (!item.style.getPropertyValue('--index')) item.style.setProperty('--index', index % 8);
        observer.observe(item);
    });
});
