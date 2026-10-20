/**
 * ConnectSphere Core Client Logic
 * Vanilla JavaScript implementation providing progressive enhancement
 */

// Helper to get CSRF cookie
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

document.addEventListener('DOMContentLoaded', () => {
  const csrftoken = getCookie('csrftoken');

  // Dismissible alerts
  document.querySelectorAll('.alert-close').forEach(btn => {
    btn.addEventListener('click', () => {
      const alert = btn.closest('.alert');
      if (alert) {
        alert.style.opacity = '0';
        setTimeout(() => alert.remove(), 200);
      }
    });
  });

  // Post composer image preview
  const postImageInput = document.querySelector('.post-image-input');
  const imagePreviewContainer = document.querySelector('.image-preview-container');
  const imagePreviewImg = document.querySelector('.image-preview-img');

  if (postImageInput && imagePreviewContainer && imagePreviewImg) {
    postImageInput.addEventListener('change', function() {
      const file = this.files[0];
      if (file) {
        const reader = new FileReader();
        reader.onload = function(e) {
          imagePreviewImg.src = e.target.result;
          imagePreviewContainer.style.display = 'block';
        };
        reader.readAsDataURL(file);
      } else {
        imagePreviewContainer.style.display = 'none';
        imagePreviewImg.src = '';
      }
    });
  }

  // Interactive Async Like Buttons
  document.querySelectorAll('.btn-like-ajax').forEach(button => {
    button.addEventListener('click', async (e) => {
      e.preventDefault();
      const postId = button.dataset.postId;
      const countSpan = button.querySelector('.like-count');
      const iconSpan = button.querySelector('.like-icon');

      if (!postId) return;

      try {
        const response = await fetch(`/posts/${postId}/like/`, {
          method: 'POST',
          headers: {
            'X-CSRFToken': csrftoken,
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json',
          }
        });

        if (response.ok) {
          const data = await response.json();
          if (data.success) {
            if (countSpan) countSpan.textContent = data.likes_count;
            if (data.liked) {
              button.classList.add('liked');
              if (iconSpan) iconSpan.textContent = '❤️';
            } else {
              button.classList.remove('liked');
              if (iconSpan) iconSpan.textContent = '🤍';
            }
          }
        }
      } catch (err) {
        console.error('Like request failed, falling back:', err);
      }
    });
  });

  // Interactive Async Bookmark Buttons
  document.querySelectorAll('.btn-bookmark-ajax').forEach(button => {
    button.addEventListener('click', async (e) => {
      e.preventDefault();
      const postId = button.dataset.postId;
      const iconSpan = button.querySelector('.bookmark-icon');
      const labelSpan = button.querySelector('.bookmark-label');

      if (!postId) return;

      try {
        const response = await fetch(`/social/posts/${postId}/bookmark/`, {
          method: 'POST',
          headers: {
            'X-CSRFToken': csrftoken,
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json',
          }
        });

        if (response.ok) {
          const data = await response.json();
          if (data.success) {
            if (data.is_bookmarked) {
              button.classList.add('bookmarked');
              if (iconSpan) iconSpan.textContent = '🔖';
              if (labelSpan) labelSpan.textContent = 'Saved';
            } else {
              button.classList.remove('bookmarked');
              if (iconSpan) iconSpan.textContent = '📑';
              if (labelSpan) labelSpan.textContent = 'Save';
            }
          }
        }
      } catch (err) {
        console.error('Bookmark request failed:', err);
      }
    });
  });

  // Confirmation dialogs on destructive actions
  document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('click', (e) => {
      const message = el.dataset.confirm || 'Are you sure you want to proceed?';
      if (!confirm(message)) {
        e.preventDefault();
      }
    });
  });
});
