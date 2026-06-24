"""
원고지 (Manuscript) — a tiny blog
Everything runs on the server. The ONLY Firebase credential this app needs
is `serviceAccountKey.json` (Firebase Admin SDK). There is no Firebase Web
API key, no client-side Firebase SDK, nothing else to set up in Firebase.

- Firestore (via the service account) stores `users` and `posts`.
- Login state is a normal signed Flask session cookie.
- Passwords are hashed with Werkzeug (never stored in plain text).
"""
import os
import json
import uuid

from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash

import firebase_admin
from firebase_admin import credentials, firestore

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_ACCOUNT_PATH = os.path.join(BASE_DIR, "serviceAccountKey.json")

USERS_COLLECTION = "users"
POSTS_COLLECTION = "posts"


def _init_firebase():
    """Initialize firebase_admin exactly once, using serviceAccountKey.json.

    Local / most hosts: drop serviceAccountKey.json next to app.py.
    Serverless hosts where you can't ship the file (e.g. Vercel) may instead
    set the env var FIREBASE_SERVICE_ACCOUNT_JSON to the *contents* of that
    same file. Either way, it's the one and only credential this app uses.
    """
    if firebase_admin._apps:
        return

    if os.path.exists(SERVICE_ACCOUNT_PATH):
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
    elif os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON"):
        cred = credentials.Certificate(
            json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT_JSON"])
        )
    else:
        raise RuntimeError(
            "serviceAccountKey.json을 app.py와 같은 폴더에 넣어주세요. "
            "(서버리스 배포라면 FIREBASE_SERVICE_ACCOUNT_JSON 환경변수에 "
            "그 파일 내용을 그대로 넣어도 됩니다.)"
        )

    firebase_admin.initialize_app(cred)


_init_firebase()
db = firestore.client()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")


def format_date(dt):
    if not dt:
        return ""
    try:
        return dt.strftime("%Y년 %m월 %d일")
    except AttributeError:
        return ""


@app.context_processor
def inject_current_user():
    if "uid" in session:
        return {
            "current_user": {
                "uid": session["uid"],
                "email": session.get("email"),
                "nickname": session.get("nickname"),
            }
        }
    return {"current_user": None}


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    docs = (
        db.collection(POSTS_COLLECTION)
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .stream()
    )
    posts = []
    for doc in docs:
        data = doc.to_dict() or {}
        data["id"] = doc.id
        data["created_at_display"] = format_date(data.get("created_at"))
        posts.append(data)
    return render_template("index.html", posts=posts)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html", error=None, form={})

    nickname = request.form.get("nickname", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    error = None
    if not nickname or not email or not password:
        error = "모든 항목을 입력해주세요."
    elif len(password) < 6:
        error = "비밀번호는 6자 이상이어야 해요."
    else:
        existing = list(
            db.collection(USERS_COLLECTION).where("email", "==", email).limit(1).stream()
        )
        if existing:
            error = "이미 가입된 이메일이에요."

    if error:
        return render_template("signup.html", error=error, form=request.form)

    uid = str(uuid.uuid4())
    db.collection(USERS_COLLECTION).document(uid).set(
        {
            "email": email,
            "nickname": nickname,
            "password_hash": generate_password_hash(password),
            "created_at": firestore.SERVER_TIMESTAMP,
        }
    )
    session["uid"] = uid
    session["email"] = email
    session["nickname"] = nickname
    return redirect(url_for("index"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", error=None, form={})

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    error = None
    user_doc = None

    matches = list(
        db.collection(USERS_COLLECTION).where("email", "==", email).limit(1).stream()
    )
    if not matches:
        error = "등록되지 않은 이메일이에요."
    else:
        user_doc = matches[0]
        data = user_doc.to_dict() or {}
        if not check_password_hash(data.get("password_hash", ""), password):
            error = "비밀번호가 일치하지 않아요."

    if error:
        return render_template("login.html", error=error, form=request.form)

    data = user_doc.to_dict() or {}
    session["uid"] = user_doc.id
    session["email"] = data.get("email")
    session["nickname"] = data.get("nickname")

    next_url = request.args.get("next") or url_for("index")
    return redirect(next_url)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/write", methods=["GET", "POST"])
def write():
    if "uid" not in session:
        return render_template("write.html", logged_in=False, error=None, form={})

    if request.method == "GET":
        return render_template("write.html", logged_in=True, error=None, form={})

    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()

    error = None
    if not title:
        error = "제목을 입력해주세요."
    elif not content:
        error = "본문을 입력해주세요."

    if error:
        return render_template("write.html", logged_in=True, error=error, form=request.form)

    doc_ref = db.collection(POSTS_COLLECTION).document()
    doc_ref.set(
        {
            "title": title,
            "content": content,
            "author_uid": session["uid"],
            "author_name": session.get("nickname") or session.get("email"),
            "created_at": firestore.SERVER_TIMESTAMP,
        }
    )
    return redirect(url_for("post_detail", post_id=doc_ref.id))


@app.route("/post/<post_id>")
def post_detail(post_id):
    doc = db.collection(POSTS_COLLECTION).document(post_id).get()
    if not doc.exists:
        return render_template("post.html", post=None), 404

    data = doc.to_dict() or {}
    data["id"] = doc.id
    data["created_at_display"] = format_date(data.get("created_at"))
    data["paragraphs"] = [p for p in (data.get("content") or "").split("\n") if p.strip()]
    return render_template("post.html", post=data)


# Vercel's Python runtime looks for a WSGI callable named `app`.
if __name__ == "__main__":
    app.run(debug=True, port=5000)
