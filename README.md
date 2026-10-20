# ConnectSphere — Industrial-Quality Social Media Platform

ConnectSphere is a full-featured, secure, responsive, and trustworthy mini social media web platform engineered with **Python**, **Django**, **HTML5**, **CSS3**, and **vanilla JavaScript**. It is built strictly following standard server-rendered Django architecture with progressive client-side enhancement without reliance on external JavaScript frameworks or paid APIs.

---

## 🌟 Key Capabilities & Features

### Core Feature 1: Authentication & Access Control
- **User Registration**: Custom registration with username validation, email uniqueness, strong password enforcement (min 8 characters, common password checks), and password confirmation.
- **Session-Based Authentication**: Secure login and logout using Django's built-in session framework.
- **Route Protection**: Private application pages protected via `@login_required` with appropriate `next` URL redirection.
- **Friendly Feedback**: Contextual flash messages for registration, login, logout, and validation errors.

### Core Feature 2: User Profiles & Privacy
- **Automatic Profile Lifecycle**: Auto-provisioning of `Profile` records via Django post-save signals upon user creation.
- **Customizable Profiles**: Display name, biography (500 chars), and avatar image upload with file type/size validation (<2MB).
- **Public & Private Accounts**: Configurable account privacy setting. When an account is private, posts are only accessible to approved followers.
- **Profile Metrics**: Live counters for total posts, followers, and following.
- **Strict Ownership**: Server-enforced permissions preventing users from editing or tampering with another user's profile.

### Core Feature 3: Posts & Dual Feed Architecture
- **Rich Posts**: Create text posts (up to 2,000 characters) and image posts (up to 5MB, format-validated).
- **Dual Feed Modes**:
  - **Following Feed**: Chronological stream of posts from accounts you follow and your own posts.
  - **Discover Feed**: Recent public posts from across the platform to discover new creators.
- **Block-Aware Filtering**: Automatically hides posts from blocked users or users who have blocked the viewer.
- **Post Management**: Full edit and delete capabilities restricted strictly to the post author.
- **Audit & Editing**: Dedicated "(edited)" indicator when post content is modified after creation.
- **Pagination**: Scalable server-side pagination (10 posts per page).
- **Empty States**: Meaningful, contextual empty states encouraging community discovery.

### Core Feature 4: Likes System
- **Like & Unlike Toggle**: Instant toggle with both AJAX progressive enhancement and server-side form fallback.
- **Duplicate Prevention**: Enforced at the database layer via `models.UniqueConstraint(fields=['user', 'post'])` and server validation.
- **Notification Trigger**: Generates an in-app notification for the author (suppressed for self-likes).

### Core Feature 5: Comments System
- **Post Discussions**: Add comments to posts with length validation (up to 1,000 characters; whitespace rejection).
- **Comment Ownership**: Authors can edit and delete their own comments with confirmation.
- **Access Protection**: Non-authors cannot modify or delete others' comments (returns `HTTP 403 Forbidden`).

### Core Feature 6: Follow System & Network
- **Follow & Unfollow**: Follow other users with instant feedback.
- **Self-Follow Prevention**: Prohibited both at the application level and via database constraint `CheckConstraint(~Q(follower=F('following')))`.
- **Duplicate Prevention**: Guaranteed via `models.UniqueConstraint(fields=['follower', 'following'])`.
- **Follower & Following Lists**: Dedicated profile navigation showing who follows whom with inline follow/unfollow actions.

---

## 🛡️ Distinctive & Advanced Features

### Priority A: Trust & Safety Center
- **Reporting System**: Users can report suspicious or harmful posts, comments, or accounts with standardized categories (`spam`, `harassment`, `hate_speech`, `inappropriate`, `misinformation`, `other`).
- **Staff Moderation Dashboard**: Restricted moderation dashboard (`/moderation/dashboard/`) protected by `is_staff` / `is_superuser` permissions.
- **Moderator Actions**: Review queue categorized by status (`pending`, `reviewed`, `action_taken`, `dismissed`) with one-click content removal capabilities.
- **User Blocking**: Block/unblock users. Blocking automatically severs any existing follow relationships in both directions and completely excludes the blocked party's content from feeds and search results.

### Priority B: Private Bookmarks
- **Save & Unsave Posts**: Bookmark posts to revisit later.
- **Strict Privacy**: Saved Posts page (`/social/saved/`) strictly displays only the authenticated user's private bookmarks.
- **Duplicate Prevention**: Database uniqueness constraint `models.UniqueConstraint(fields=['user', 'post'])`.

### Priority C: In-App Notifications
- **Event-Driven Alerts**: Notifications for new followers, post likes, and comments.
- **Anti-Spam & Idempotency**: Suppresses self-notifications and prevents duplicate unread notifications for repeated actions.
- **Notification Center**: Header bell icon with real-time unread badge counter, individual "Mark read" controls, and "Mark all as read".

### Priority D: Low-Bandwidth Mode
- **Low-Bandwidth Setting**: Accessible in profile preferences. Disables heavy CSS animations, removes shadows, and optimizes rendering for slow connections or low-power devices.

### Priority E: User Experience & Search
- **User Search**: Instant search by username or display name with direct follow action buttons.
- **Accessible Design System**: WCAG-compliant color contrast, clean semantic HTML5, visible focus rings, and responsive navigation.

---

## 🛠️ Mandatory Technology Stack

| Component | Technology |
|---|---|
| **Backend** | Python 3.13+, Django 6.1.2 |
| **Database** | SQLite 3 with Django ORM & Migrations |
| **Frontend** | HTML5, CSS3 (Custom Design System), Vanilla JavaScript (ES6+) |
| **Media Handling** | Pillow 12.2.0 |
| **Version Control** | Git |
| **Testing** | Django Automated Test Suite (`django.test.TestCase`, `Client`) |

---

## 📂 Project Architecture

```
social media platform/
├── manage.py
├── requirements.txt
├── .gitignore
├── .env.example
├── db.sqlite3
├── config/                  # Core project configuration
│   ├── settings.py          # Environment-aware settings, security flags, apps
│   ├── urls.py              # Central URL routing
│   ├── wsgi.py
│   └── asgi.py
├── accounts/                # Authentication, profiles, user search
│   ├── models.py            # Profile model with auto-provisioning signal
│   ├── forms.py             # UserRegistrationForm, ProfileEditForm
│   ├── views.py             # register, login, logout, profile, search
│   ├── urls.py
│   ├── context_processors.py# Preferences (low-bandwidth) context processor
│   └── tests.py             # Auth & profile automated tests
├── posts/                   # Posts, likes, comments, and feed
│   ├── models.py            # Post, Like, Comment models with constraints
│   ├── forms.py             # PostCreateForm, PostEditForm, CommentForm
│   ├── views.py             # feed, create, edit, delete, like, comment
│   ├── urls.py
│   ├── management/commands/ # seed_demo_data command
│   └── tests.py             # Feed, posts, likes, comments automated tests
├── social/                  # Follows, bookmarks, and user blocking
│   ├── models.py            # Follow, Bookmark, Block models with check constraints
│   ├── utils.py             # Block checking & relationship helpers
│   ├── views.py             # follow, saved_posts, block, followers/following
│   ├── urls.py
│   └── tests.py             # Follow, bookmark, block automated tests
├── notifications/           # In-app notification system
│   ├── models.py            # Notification model
│   ├── utils.py             # Safe notification creator helper
│   ├── context_processors.py# Unread notification badge processor
│   ├── views.py             # notification_list, mark_as_read, mark_all_read
│   ├── urls.py
│   └── tests.py             # Notification automated tests
├── moderation/              # Trust & Safety reporting and staff moderation
│   ├── models.py            # Report model with status tracking
│   ├── forms.py             # ReportForm, ModerationActionForm
│   ├── views.py             # report submission, staff dashboard & review
│   ├── urls.py
│   └── tests.py             # Reporting & staff access tests
├── static/
│   ├── css/style.css        # Curated responsive design system & low-bandwidth rules
│   └── js/main.js           # Vanilla JS: async likes/bookmarks, image preview, alerts
├── templates/
│   ├── base.html            # Master layout with semantic header, nav, alerts
│   ├── accounts/            # register, login, profile, profile_edit, user_search
│   ├── posts/               # feed, post_detail, post_edit, post_confirm_delete, etc.
│   ├── social/              # follow_list, saved_posts, blocked_users
│   ├── notifications/       # notification_list
│   └── moderation/          # report_form, dashboard, review
└── media/                   # User-uploaded profile avatars and post images
```

---

## 🚀 Setup & Installation Instructions

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.13)
- Git

### 2. Clone and Setup Environment
```bash
# Clone the repository
git clone <repository-url>
cd "social media platform"

# Create a virtual environment (optional but recommended)
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux / macOS:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
python -m pip install -r requirements.txt
```

### 4. Environment Configuration
Create a `.env` file based on `.env.example`:
```bash
# Windows PowerShell
Copy-Item .env.example .env
```

### 5. Apply Database Migrations
```bash
python manage.py migrate
```

### 6. Seed Demo Data (Recommended for Evaluators)
Populate realistic users, follow graphs, rich posts, likes, comments, and notifications with a single command:
```bash
python manage.py seed_demo_data
```

### 7. Run the Application
```bash
python manage.py runserver 127.0.0.1:8000
```
Open your browser and navigate to **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)**.

---

## 🔑 Pre-Configured Demo Accounts

All seeded demo accounts use the standard password format:

| Role | Username | Password | Notes |
|---|---|---|---|
| **Admin / Moderator** | `admin` | `Admin@12345` | Staff user with access to `/moderation/dashboard/` |
| **Creator 1** | `sophia_dev` | `Password@123` | Full feed with followers, notifications, and posts |
| **Creator 2** | `marcus_ai` | `Password@123` | AI researcher with public posts |
| **Creator 3** | `elena_design` | `Password@123` | Product designer with public posts |
| **Private Account** | `alex_coder` | `Password@123` | Demonstrates private account privacy enforcement |

---

## 🧪 Automated Testing Suite

The project includes 36 thorough automated test cases covering registration, authentication, permissions, CRUD ownership, duplicate constraints, feed filtering, bookmarks, blocking, deep image verification, and moderation.

### Run Tests:
```bash
python manage.py test
```

### Test Results Summary:
```
Ran 36 tests in 124.364s

OK
Destroying test database for alias 'default'...
Found 36 test(s).
System check identified no issues (0 silenced).
```

### System Integrity & Deployment Check:
```bash
# Standard system check
python manage.py check
# Result: System check identified no issues (0 silenced).

# Production deployment readiness check
python manage.py check --deploy
```

---

## 🧭 Evaluator Demonstration Walkthrough

1. **Sign In**:
   - Navigate to `/accounts/login/` and sign in as `sophia_dev` (`Password@123`).
2. **Home Feed**:
   - Notice the profile snippet on the left, feed mode tabs, post composer, and post stream.
   - Switch between **Following** and **Discover** tabs.
3. **Publishing a Post**:
   - In the composer, enter a message and optionally attach an image (`.png`, `.jpg`).
   - Click **Share Post** — observe the post appears at the top of the feed immediately.
4. **Interactions**:
   - Click the **❤️ Like** button on a post. The count increments via async fetch without page reload.
   - Click the **💬 Discussion** link to open the post detail view and add a comment.
   - Click the **📑 Save** button to bookmark the post.
5. **Private Bookmarks**:
   - Click **Saved** in the navigation header to verify that only your bookmarked posts are displayed.
6. **In-App Notifications**:
   - Click **Notifications** in the navbar. Observe unread notifications with timestamps and actor details. Click **✓ Mark all as read**.
7. **User Profile & Privacy**:
   - Click **@sophia_dev** in the navbar to view your profile, post history, and follower counters.
   - Click **✏️ Edit Profile** to change bio, toggle **Private Account**, or enable **Low-Bandwidth Mode**.
8. **Trust & Safety / Moderation**:
   - Log out and log in as `admin` (`Admin@12345`).
   - Click **🛡️ Moderation** in the header to view the Trust & Safety review queue and test resolving reported violations.

---

## 🔒 Security Architecture & Considerations

- **CSRF Protection**: Standard Django CSRF tokens on all state-changing `POST` forms and asynchronous `fetch` headers (`X-CSRFToken`).
- **Authorization & Ownership**: All edit and delete routes explicitly verify content ownership (`post.author == request.user`, `comment.author == request.user`) before processing, returning `HTTP 403 Forbidden` if breached.
- **SQL Injection Prevention**: 100% parameterization using Django ORM; no raw concatenated SQL.
- **XSS Mitigation**: Strict Django template autoescaping prevents HTML/script injection from user-generated content.
- **File Upload Security**:
  - Image file extensions validated against `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`.
  - Image size restricted to < 5MB for posts, < 2MB for profile avatars.
- **Production Hardening**: When `DJANGO_DEBUG=False`, automatic activation of `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT`, and `SECURE_HSTS_SECONDS`.

---

## 📄 License & Attribution
Developed as part of the ConnectSphere engineering assignment. Built with craftsmanship following Django and Web standards.
