import json
from os import environ as env
from urllib.parse import quote_plus, urlencode

from authlib.integrations.flask_client import OAuth
from dotenv import find_dotenv, load_dotenv
from flask import Flask, redirect, render_template, session, url_for, request
import db_helper as db
import boto3
from flask_apscheduler import APScheduler

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

app = Flask(__name__)
app.secret_key = env.get("APP_SECRET_KEY")



oauth = OAuth(app)

oauth.register(
    "auth0",
    client_id=env.get("AUTH0_CLIENT_ID"),
    client_secret=env.get("AUTH0_CLIENT_SECRET"),
    client_kwargs={
        "scope": "openid profile email",
    },
    server_metadata_url=f'https://{env.get("AUTH0_DOMAIN")}/.well-known/openid-configuration',
)
s3_client = boto3.client(
    "s3",
    aws_access_key_id=env.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=env.get("AWS_SECRET_ACCESS_KEY"),
    region_name=env.get("S3_REGION")
)

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()





@app.route("/")
def home():
    return render_template(
        "home.html",
        session=session.get("user"),
        pretty=json.dumps(session.get("user"), indent=4),
    )

@app.route('/art/<id>')
def art(id):
    #put into interaction db for viewed/
    if 'user' in session and 'userinfo' in session['user']:
        user_id = session['user']['userinfo'].get('user_id')
        viewd = db.query_db(
            "SELECT * FROM image_interactions WHERE user_id = %s AND image_id = %s", (user_id, id),one=True
        )

        if user_id and not viewd:
            db.modify_db(
                "INSERT INTO image_interactions (user_id, image_id, viewed) VALUES (%s, %s, TRUE)",
                (user_id, id),
            )
    return render_template('art_page.html', session=session.get("user"), art_id=id)

@app.route("/user_profile")
def user_profile():
    # Check if user data is in the session
    user_info = session.get('user')
    
    if not user_info:
        # Redirect to login page or handle the case where there is no user info
        return redirect(url_for('login'))

    # Assuming the user_info contains all the necessary data
    user_id = user_info['userinfo']['user_id']
    print("user_id:",user_id, flush=True)
    
    user_data = {
        'name': user_info['userinfo']['name'],  
        'email': user_info['userinfo']['email'],  
        'description': get_user_description(user_id),  # Store this in the session or database as well
        'subscriptions': get_user_subscriptions(user_id),  
        'fans': get_user_fans(user_id),  
        'likes': get_user_likes(user_id),  # This should come from the database or session
    #     'artworks': [
    #     {'title': 'Artwork 1', 'url': 'images/sample.png'},
    #     {'title': 'Artwork 2', 'url': 'images/art.png'},
    #     {'title': 'Artwork 3', 'url': 'images/sample.png'},
    # ]
        'artworks': get_user_artworks(user_id)
    }
    return render_template('user_profile.html', user=user_data)

def get_user_description(user_id):
    description = db.query_db(
        "SELECT description FROM descriptions WHERE user_id = %s", (user_id,),one=True
    )
    return description[0] if description else "No description yet"
def get_user_likes(user_id):
    likes = db.query_db(
        "SELECT COUNT(*) FROM image_interactions WHERE user_id = %s AND liked = TRUE", (user_id,),one=True
    )
    return likes[0] if likes else 0
def get_user_fans(user_id):
    fans = db.query_db(
        "SELECT COUNT(*) FROM follows WHERE following_id = %s", (user_id,),one=True
    )
    return fans[0] if fans else 0
def get_user_subscriptions(user_id):
    subscriptions = db.query_db(
        "SELECT COUNT(*) FROM follows WHERE follower_id = %s", (user_id,),one=True
    )
    return subscriptions[0] if subscriptions else 0

def get_user_artworks(user_id):
    artworks = db.query_db(
        "SELECT * FROM images WHERE user_id = %s", (user_id,)
    )
    print("artworks:",artworks, flush=True)
    return artworks

def get_trending_artworks():

    sql = """
    SELECT i.*,
           (COUNT(ii.user_id) FILTER (WHERE ii.liked) + 1) / 
           POWER(EXTRACT(EPOCH FROM NOW() - i.created_at) / 3600 + 1, 1.8) AS score
    FROM images i
    LEFT JOIN image_interactions ii ON i.image_id = ii.image_id
    GROUP BY i.image_id
    ORDER BY score DESC
    LIMIT 10;
    """
    artworks = db.query_db(sql)
    return artworks
def get_most_liked():
    sql = """
    SELECT i.*,
           COUNT(ii.user_id) FILTER (WHERE ii.liked) AS likes
    FROM images i
    LEFT JOIN image_interactions ii ON i.image_id = ii.image_id
    GROUP BY i.image_id
    ORDER BY likes DESC
    LIMIT 10;
    """
    artworks = db.query_db(sql)
    return artworks
def get_most_viewed():
    sql = """
    SELECT i.*,
           COUNT(ii.user_id) FILTER (WHERE ii.viewed) AS views
    FROM images i
    LEFT JOIN image_interactions ii ON i.image_id = ii.image_id
    GROUP BY i.image_id
    ORDER BY views DESC
    LIMIT 10;
    """
    artworks = db.query_db(sql)
    return artworks
@scheduler.task('cron', id='calcular_similarity', hour=3, minute=0, misfire_grace_time=900)
def calcular_similarity():
    #TODO
    pass
def get_recent_artworks():
    #TODO
    pass


def get_friends_work(user_id):

    sql = """
    SELECT images.*
    FROM images
    JOIN follows ON follows.following_id = images.user_id
    LEFT JOIN image_interactions ON image_interactions.image_id = images.image_id AND image_interactions.user_id = follows.follower_id
    WHERE follows.follower_id = %s
    AND image_interactions.viewed = FALSE
    ORDER BY images.created_at DESC;
    """
    artworks = db.query_db(sql, (session['user']['userinfo']['user_id']))
    return artworks







@app.route('/comments', methods=['GET','POST'])
#ajax?
def comments():
    if request.method == 'POST':
        comment = request.form.get('comment')
        image_id = request.form.get('image_id')
        user_id = session['user']['userinfo']['user_id']
        db.modify_db(
            "INSERT INTO comments (user_id, image_id, comment) VALUES (%s, %s, %s)",
            (user_id, image_id, comment),
        )
        return redirect(url_for('art', id=image_id))
    else:
        image_id = request.args.get('image_id')
        comments = db.query_db(
            "SELECT * FROM comments WHERE image_id = %s", (image_id,)
        )
        return comments
@app.route('/like', methods=['POST'])   
def like():
    image_id = request.form.get('image_id')
    user_id = session['user']['userinfo']['user_id']
    #find the interaction and update
    db.modify_db(
        "update image_interactions set liked = TRUE where user_id = %s and image_id = %s",
        (user_id, image_id),
    )
    return "success",200
    
        
@app.route('/update_description', methods=['POST'])
def update_description():
    # # Make sure the user is logged in
    # if 'user' in session and session['user']:
    #     new_description = request.form.get('description')
    #     # Update
    #     session['user']['description'] = new_description
        
    #     # Redirect back to the profile page
    #     return redirect(url_for('user_profile'))
    # else:
    #     return redirect(url_for('login'))
    new_description = request.form.get('description')
    user_id = session['user']['userinfo']['user_id']
    search_result = db.query_db(
        "SELECT description FROM descriptions WHERE user_id = %s", (user_id,),one=True
    )
    if search_result:
        db.modify_db(
            "UPDATE descriptions SET description = %s WHERE user_id = %s",
            (new_description, user_id),
        )
    else:
        db.modify_db(
            "INSERT INTO descriptions (user_id, description) VALUES (%s, %s)",
            (user_id, new_description),
        )
    return redirect(url_for('user_profile'))

#fuzzy search
@app.route('/search')
def search():
    search_query = request.args.get('query', '')  # Get the search query from the URL parameters
    results = db.query_db("""
        SELECT image_id, title, description, image_url
        FROM images
        WHERE to_tsvector('english', title || ' ' || description || ' ' || prompt) @@ plainto_tsquery('english', %s)
        ORDER BY ts_rank(to_tsvector('english', title || ' ' || description || ' ' || prompt), plainto_tsquery('english', %s)) DESC
        LIMIT 10;
    """, (search_query, search_query))
    return render_template('search_results.html', results=results)

def some_route_function():
    image_path_art = url_for('static', filename='images/art.png')
    image_path_sample = url_for('static', filename='images/sample.png')
    # Now you can pass these paths to your template
    return render_template('your_template.html', art_image=image_path_art, sample_image=image_path_sample)

@app.route("/login")
def login():
    return oauth.auth0.authorize_redirect(
        redirect_uri=url_for("callback", _external=True)
    )

@app.route("/callback", methods=["GET", "POST"])
def callback():
    token = oauth.auth0.authorize_access_token()
    session["user"] = token

    user_info = token['userinfo']
    store_new_user(user_info)
    return redirect("/")

def store_new_user(user_info):
    userID = db.query_db(
        "SELECT user_id FROM users WHERE auth0_user_id = %s", (user_info["sub"],), one=True
    )
    if userID is None:
        db.modify_db(
            "INSERT INTO users (auth0_user_id, email) VALUES (%s, %s)",
            (user_info["sub"], user_info["email"]),
        )
        userID = db.query_db(
            "SELECT user_id FROM users WHERE auth0_user_id = %s", (user_info["sub"],), one=True
        )

    #get user id from db and store in session
    # print("userID:",userID[0], flush=True)
    
    session['user']['userinfo']['user_id'] = userID[0]
        
    return





@app.route("/logout")
def logout():
    session.clear()
    return redirect(
        "https://"
        + env.get("AUTH0_DOMAIN")
        + "/v2/logout?"
        + urlencode(
            {
                "returnTo": url_for("home", _external=True),
                "client_id": env.get("AUTH0_CLIENT_ID"),
            },
            quote_via=quote_plus,
        )
    )

@app.route("/upload", methods=["GET", "POST"])
def upload_image():
    if "user" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        if 'image' not in request.files:
            return "No file part", 400
        image = request.files['image']
        if image.filename == '':
            return "No selected file",  400
        if image:
            image_url = upload_image_to_s3(image)
            title = request.form.get("title", "")
            description = request.form.get("description", "")
            prompt = request.form.get("prompt", "")
            user_id = session["user"]["user_id"] 
            # user_id = 1
            db.modify_db(
                "INSERT INTO images (user_id, title, description, image_url, prompt) VALUES (%s, %s, %s, %s, %s)",
                (user_id, title, description, image_url, prompt),
            )
            return 'Image uploaded successfully!', 200
    return render_template("upload.html")


def upload_image_to_s3(image):
    s3_client.upload_fileobj(
        image,
        env.get("S3_BUCKET"),
        image.filename,
        ExtraArgs={"ContentType": image.content_type},
    )
    return f"https://{env.get('S3_BUCKET')}.s3.amazonaws.com/{image.filename}"

###############




# 模拟的用户数据
users = {
    "following": [
        {"id": 1, "name": "Alice", "bio": "Loves art and photography", "avatar_url": "https://example.com/avatar/alice.jpg"},
        {"id": 2, "name": "Bob", "bio": "Music enthusiast and guitar player", "avatar_url": "https://example.com/avatar/bob.jpg"},
    ],
    "followers": [
        {"id": 3, "name": "Charlie", "bio": "Tech geek and blogger", "avatar_url": "https://example.com/avatar/charlie.jpg"},
        {"id": 4, "name": "Dana", "bio": "Adventure lover and book reader", "avatar_url": "https://example.com/avatar/dana.jpg"},
    ]
}

@app.route('/user/following')
def show_following():
    user_info = session.get('user')
    if not user_info or 'userinfo' not in user_info or 'user_id' not in user_info['userinfo']:
        # 如果用户未登录或session中不存在用户信息，重定向到登录页面
        return redirect(url_for('login'))

    user_id = user_info['userinfo']['user_id']

    # 查询当前用户关注的人
    following_sql = """
    SELECT u.user_id, u.email, f.created_at
    FROM follows f
    JOIN users u ON f.following_id = u.user_id
    WHERE f.follower_id = %s;
    """
    following = db.query_db(following_sql, (user_id,))

    # 查询关注当前用户的人
    followers_sql = """
    SELECT u.user_id, u.email, f.created_at
    FROM follows f
    JOIN users u ON f.follower_id = u.user_id
    WHERE f.following_id = %s;
    """
    followers = db.query_db(followers_sql, (user_id,))
    print("xxxxxx")
    print(following)  # 这将在服务器的控制台上打印following列表


    return render_template('follows.html', following=following, followers=followers)

##############

if __name__ == "__main__":
    with app.app_context():
        db.init_db_pool()
    app.run(debug=True)
    # app.run(host="0.0.0.0", port=env.get("PORT", 3000))
