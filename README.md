# 원고지 — 회원가입 & 글쓰기 블로그 (serviceAccountKey.json만 사용)

Flask + Firebase **Admin SDK**로만 만든 블로그입니다.
Firebase에서 필요한 건 **`serviceAccountKey.json` 딱 하나**뿐이에요.
Firebase Web API 키, Firebase Authentication 설정, 클라이언트 SDK 같은 건
전혀 쓰지 않습니다. 로그인/회원가입/세션은 전부 Flask 서버 코드가 직접
처리하고, Firestore는 데이터를 저장하는 용도로만 사용해요.

## 어떻게 동작하나요

- **회원가입**: 입력한 이메일/비밀번호를 서버에서 받아 비밀번호는
  Werkzeug로 안전하게 해시 처리한 뒤 Firestore `users` 컬렉션에 저장
- **로그인**: 이메일로 Firestore에서 사용자를 찾아 비밀번호 해시를 비교,
  맞으면 Flask 세션 쿠키 발급
- **글쓰기**: 로그인한 사용자만 `/write` 페이지에서 글 작성 가능,
  Firestore `posts` 컬렉션에 저장
- **글 목록/상세**: 누구나 열람 가능 (서버에서 Firestore를 조회해 그려줌)

## 폴더 구조

```
blog-app/
├── app.py                  # Flask 서버 (라우팅 + 로그인/회원가입/글 작성 전부 포함)
├── requirements.txt         # Flask, firebase-admin
├── vercel.json               # Vercel 배포 설정
├── serviceAccountKey.json    # ← 직접 넣어주세요 (아래 1번 참고, git에는 올리지 않음)
├── firestore.rules           # 참고용 (Admin SDK만 쓰면 적용 안 해도 무방)
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── signup.html
│   ├── write.html
│   └── post.html
└── static/
    ├── css/style.css         # 반응형 디자인 (원고지 모티프)
    └── js/main.js             # 모바일 메뉴 토글 + 글자 수 카운터뿐, Firebase 무관
```

## 1. serviceAccountKey.json 발급받기

1. https://console.firebase.google.com 에서 프로젝트 생성 (또는 기존 프로젝트 사용)
2. **Firestore Database** 메뉴에서 데이터베이스 생성 (모드는 자유롭게 — 어차피
   Admin SDK는 규칙을 무시하고 항상 전체 권한으로 접근합니다)
3. **프로젝트 설정(⚙) → 서비스 계정 → 새 비공개 키 생성** 클릭
4. 다운로드된 JSON 파일 이름을 `serviceAccountKey.json`으로 바꿔서
   `app.py`와 같은 폴더(프로젝트 루트)에 넣기

이 파일 하나면 끝입니다. 다른 Firebase 설정은 필요 없어요.

> ⚠️ 이 파일은 서버의 모든 권한을 가진 비밀 키예요. 절대 GitHub에
> 커밋하지 마세요. `.gitignore`에 이미 `serviceAccountKey.json`이
> 등록되어 있어 `git add .`를 해도 함께 올라가지 않습니다.

## 2. 로컬에서 실행하기

```bash
cd blog-app
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# serviceAccountKey.json을 이 폴더에 넣었는지 확인한 뒤:
python app.py
# http://127.0.0.1:5000 접속
```

## 3. GitHub에 올리기

```bash
cd blog-app
git init
git add .
git commit -m "원고지 블로그 초기 커밋"
git branch -M main
git remote add origin https://github.com/<your-id>/<repo-name>.git
git push -u origin main
```

`serviceAccountKey.json`은 `.gitignore`로 제외되어 있어 저장소에는
올라가지 않습니다 (의도된 동작이에요).

## 4. Vercel에 배포하기

Vercel은 깃허브 저장소를 그대로 빌드하기 때문에, git에 올리지 않은
`serviceAccountKey.json`을 서버가 읽을 방법이 따로 필요합니다.
**그 JSON 파일의 내용 전체를 환경변수 하나에 그대로 붙여넣는 방식**을
씁니다 (파일을 추가하는 게 아니라 내용만 복사하는 거라, "Firebase에서
serviceAccountKey.json 외에 다른 걸 더 설정한다"는 의미는 아니에요).

1. https://vercel.com → **Add New → Project** → GitHub 저장소 선택
2. Framework Preset이 자동 감지되지 않으면 **Other** 선택
   (`vercel.json`이 Python 빌드를 지정합니다)
3. **Environment Variables**에 아래 2개 추가:
   - `FIREBASE_SERVICE_ACCOUNT_JSON` → `serviceAccountKey.json` 파일을
     열어서 내용 전체(중괄호 `{` 부터 `}` 까지)를 그대로 복사해 붙여넣기
   - `FLASK_SECRET_KEY` → 세션 쿠키 서명용 임의의 긴 문자열
     (예: `python -c "import secrets; print(secrets.token_hex(32))"` 로 생성)
4. **Deploy** 클릭

로컬에서는 파일(`serviceAccountKey.json`)을, 배포 환경에서는 환경변수
(`FIREBASE_SERVICE_ACCOUNT_JSON`)를 — `app.py`가 둘 중 있는 걸 자동으로
찾아서 씁니다.

## 커스터마이징 팁

- `static/css/style.css` 최상단 `:root` 변수만 바꿔도 전체 색감을 바꿀 수 있어요.
- 글에 이미지/카테고리/좋아요 등을 추가하려면 `app.py`의 `write()`,
  `index()`, `post_detail()` 함수와 해당 템플릿만 함께 확장하면 됩니다.
- 세션은 Flask의 서명된 쿠키를 사용해요. 운영 환경에서는 꼭
  `FLASK_SECRET_KEY`를 직접 정한 값으로 바꿔주세요 (기본값은 개발용입니다).
