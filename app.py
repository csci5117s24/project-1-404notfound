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

with app.app_context():
        db.init_db_pool()

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
    # Fetch the artwork data
    most_viewed = get_most_viewed()
    trending = get_trending_artworks()
    most_liked = get_most_liked()

    # Convert each list of tuples to a list of dictionaries
    def convert_to_dicts(artworks):
        return [
            {"image_id": art[0], "user_id": art[1], "title": art[2], "description": art[3], "image_url": art[4]}
            for art in artworks
        ]

    all_arts = [
        {"name": "Trending Artworks", "artworks": convert_to_dicts(trending)},
        {"name": "Most Liked Artworks", "artworks": convert_to_dicts(most_liked)},
        {"name": "Most Viewed Artworks", "artworks": convert_to_dicts(most_viewed)},
    ]
    
    
    return render_template(
        "home.html",
        session=session.get("user"),
        pretty=json.dumps(session.get("user"), indent=4),
        artworks=all_arts
    )

@app.route('/art/<id>')
def art(id):
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

    image_details = db.query_db(
        "SELECT image_id, title, description, image_url, prompt, user_id FROM images WHERE image_id = %s", (id,), one=True
    )
    author_details = db.query_db(
        "SELECT user_name, profile_pic_url FROM users WHERE user_id = %s", (image_details[5],), one=True
    )
    print("author_details:",author_details, flush=True)

    comments = db.query_db(
        "SELECT comment_id, image_id, user_id, comment FROM comments WHERE image_id = %s", (id,)
    )

    if 'user' in session and 'userinfo' in session['user']:
        following = db.query_db(
            "SELECT EXISTs (SELECT following_id FROM follows WHERE follower_id = %s AND following_id = %s)",(user_id,image_details[5])
        )

    if image_details:
        image_obj = {
            "image_id": image_details[0],
            "title": image_details[1],
            "description": image_details[2],
            "image_url": image_details[3],
            "prompt": image_details[4],
            "user_id": image_details[5]
        }
    else:
        image_obj = None  # or an appropriate error handling/response

    if author_details:
        author_obj = {
            "user_name": author_details[0],
            "profile_pic_url": author_details[1]
        }
    else:
        image_obj = None  # or an appropriate error handling/response

    comments_obj = []
    for row in comments:
        comments_obj.append({
            "comment_id": row[0],
            "image_id": row[1],
            "user_id": row[2],
            "comment": row[3]
        })
    try:
        is_liked = check_like(image_details[0], session['user']['userinfo'].get('user_id'))[0]
        user_id = session['user']['userinfo'].get('user_id')
    except:
        is_liked = False
        user_id = -1
    print("is_liked", is_liked)
    return render_template('art_page.html', is_liked = is_liked, session=session.get("user"), image_details=image_obj, comments=comments_obj,author_details=author_obj, user_id = user_id)
    

@app.route("/users/<id>")
def other_user_profile(id):
    user_id = id
    user_data = {
        'name': get_user_name(user_id),  
        'email': get_user_email(user_id),  
        'description': get_user_description(user_id),  # Store this in the session or database as well
        'subscriptions': get_user_subscriptions(user_id),  
        'fans': get_user_fans(user_id),  
        'likes': get_user_likes(user_id),  # This should come from the database or session
        'artworks': get_user_artworks(user_id),
        'profile_pic_url': get_user_profile_pic(user_id),
        'user_id': int(id)
    }
    print(id)
    print(user_data['profile_pic_url'])
    return render_template('user_profile.html', user=user_data,session=session.get("user"))

@app.route("/user_profile")
def user_profile():
    # Check if user data is in the session
    user_info = session.get("user")
    
    if not user_info:
        # Redirect to login page or handle the case where there is no user info
        return redirect(url_for('login'))

    # Assuming the user_info contains all the necessary data
    user_id = user_info['userinfo']['user_id']
    
    user_data = {
        'name': get_user_name(user_id),  
        'email': get_user_email(user_id),  
        'description': get_user_description(user_id),  # Store this in the session or database as well
        'subscriptions': get_user_subscriptions(user_id),  
        'fans': get_user_fans(user_id),  
        'likes': get_user_likes(user_id),  # This should come from the database or session
        'artworks': get_user_artworks(user_id),
        'profile_pic_url': get_user_profile_pic(user_id),
        'user_id': user_id
    }
    return render_template('user_profile.html', user=user_data,session=session.get('user'))

def get_user_email(user_id):
    email = db.query_db(
        "SELECT email FROM users WHERE user_id = %s", (user_id,),one=True
    )
    return email[0] if email else "No email"
def get_user_name(user_id):
    name = db.query_db(
        "SELECT user_name FROM users WHERE user_id = %s", (user_id,),one=True
    )
    return name[0] if name else "No name"

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
    return artworks
def get_user_profile_pic(user_id):
    profile_pic = db.query_db(
        "SELECT profile_pic_url FROM users WHERE user_id = %s", (user_id,),one=True
    )
    return profile_pic[0] if profile_pic else "No profile pic"


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

def check_follow(follower_id, following_id):
    result = db.query_db(
        "SELECT * FROM follows WHERE follower_id = %s AND following_id = %s", (follower_id, following_id)
    )
    is_following = len(result) > 0
    if (is_following):
        print("Following")
    else:
        print("Not following")
    return is_following

@app.route('/api/follow/', methods=['POST'])
def follow_user():
    data = request.get_json()  # Parse the JSON data sent in the request body

    follower_id = data.get('follower_id')
    following_id = data.get('following_id')
    print("api follow")
    print("follower_id", follower_id)
    print("following_id", following_id)
    if check_follow(follower_id, following_id):
        return {"success": False, "following": True,"message": "You are following the user already"}
    try:
        db.modify_db(
            "INSERT INTO follows (follower_id, following_id) VALUES (%s, %s)",
            (follower_id, following_id)
        )
        return {"success": True, "following": True, "message": "Follow successful."}
    except Exception as e:
        # Handle any database errors or exceptions
        return {"success": False, "following": False, "message": f"An error occurred: {str(e)}"}

@app.route('/api/unfollow/', methods=['POST'])
def unfollow_user():
    data = request.get_json()  # Parse the JSON data sent in the request body

    follower_id = data.get('follower_id')
    following_id = data.get('following_id')
    print("api unfollow")
    print("follower_id", follower_id)
    print("following_id", following_id)
    if check_follow(follower_id, following_id) != True:
        return {"success": False, "following": False,"message": "You didn't follow the user"}
    try:
        db.modify_db(
            "DELETE FROM follows WHERE follower_id = %s AND following_id = %s",
            (follower_id, following_id)
        )
        return {"success": True, "following": False, "message": "Unfollow successful."}
    except Exception as e:
        return {"success": False, "following": True, "message": f"An error occurred: {str(e)}"}

def check_like(image_id, user_id):
    like = db.query_db(
        "SELECT liked FROM image_interactions WHERE user_id = %s AND image_id = %s", (user_id, image_id)
    )
    print("Check like", like[0])
    return like[0]

@app.route('/api/like/', methods=['POST'])
def like_image():
    data = request.get_json()
    image_id = data.get('image_id')
    user_id = data.get('user_id')
    print("image_id", image_id)
    print("user_id", user_id )
    if check_like(image_id, user_id)[0]:
        return {"success": False, "like": True,"message": "You are liking the image already"}
    try:
        db.modify_db(
            "update image_interactions set liked = TRUE where user_id = %s and image_id = %s",
            (user_id, image_id),
        )
        return {"success": True, "like": True, "message": "Like successful."}
    except Exception as e:
        # Handle any database errors or exceptions
        return {"success": False, "like": False, "message": f"An error occurred: {str(e)}"}

@app.route('/api/unlike/', methods=['POST'])
def unlike_image():
    data = request.get_json()
    image_id = data.get('image_id')
    user_id = data.get('user_id')
    if check_like(image_id, user_id)[0] == False:
        return {"success": False, "like": False,"message": "You are not liking the image yet"}
    try:
        db.modify_db(
            "update image_interactions set liked = FALSE where user_id = %s and image_id = %s",
            (user_id, image_id),
        )
        return {"success": True, "like": False, "message": "Unlike successful."}
    except Exception as e:
        # Handle any database errors or exceptions
        return {"success": False, "like": True, "message": f"An error occurred: {str(e)}"}
    

@app.route('/comments', methods=['GET','POST'])
#ajax?
def comments():
    if request.method == 'POST':
        comment = request.form.get('comment','')
        image_id = request.form.get('image_id')
        user_id = session['user']['userinfo'].get('user_id')
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

        '''user_id = session['user']['userinfo'].get('user_id')
        user_profile_pic = db.query_db(
            "SELECT profile_pic_url FROM users WHERE user_id = %s", (user_id,), one=True
        )
        # Assuming you need to get other data as well for the 'art_page.html'
        art_details = db.query_db(
            "SELECT * FROM images WHERE image_id = %s", (image_id,), one=True
        )
        #return comments
        return render_template('art_page.html', comments=comments, art=art_details, user_profile_pic=user_profile_pic)'''
        return comments

@app.route('/like', methods=['GET','POST'])   
def like():
    if request.method == 'POST':
        image_id = request.form.get('image_id')
        user_id = session['user']['userinfo']['user_id']
        #find the interaction and update
        db.modify_db(
            "update image_interactions set liked = TRUE where user_id = %s and image_id = %s",
            (user_id, image_id),
        )
        return "success",200
    else:
        image_id = request.args.get('image_id')
        user_id = session['user']['userinfo']['user_id']
        #find the interaction and update
        like = db.query_db(
            "SELECT liked FROM image_interactions WHERE user_id = %s AND image_id = %s", (user_id, image_id)
        )
        return like[0]

@app.route('/delete-artwork/<artwork_id>', methods=['DELETE'])
def delete_artwork(artwork_id):
    # Logic to delete the artwork from the database
    success = delete_artwork_from_db(artwork_id)

    if success:
        return 'Artwork deleted successfully', 200
    else:
        # This could mean the artwork did not exist or there was a problem with the deletion
        return 'Artwork not found or could not be deleted', 404

def delete_artwork_from_db(artwork_id):
    try:
        cursor = db.modify_db(
            "DELETE FROM images WHERE image_id = %s", (artwork_id,)
        )
        # Assuming db.query_db gives you a cursor or similar object from which you can get affected rows
        affected_rows = cursor
        if affected_rows > 0:
            return True
        else:
            return False
    except Exception as e:
        print(f"Error deleting artwork: {e}")
        return False
 
@app.route('/update_description', methods=['POST'])
def update_description():
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
        SELECT image_id, title, description,image_url
        FROM images
        WHERE to_tsvector('english', title || ' ' || description || ' ' || prompt) @@ plainto_tsquery('english', %s)
        ORDER BY ts_rank(to_tsvector('english', title || ' ' || description || ' ' || prompt), plainto_tsquery('english', %s)) DESC
        LIMIT 10;
    """, (search_query, search_query))

    results_art = []
    for row in results:
        results_art.append({
            "image_id": row[0],
            "title": row[1],
            "description": row[2],
            "image_url": row[3]
        })

    result = [{"name": "Search Result", "artworks": results_art}]
    return render_template('home.html', session=session.get("user"), artworks=result)

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
    if userID:
        db.modify_db(
            "UPDATE users SET profile_pic_url = %s , user_name = %s WHERE user_id = %s;", (user_info["picture"],user_info["name"], userID[0])
        )
    if userID is None:
        db.modify_db(
            "INSERT INTO users (auth0_user_id, email,profile_pic_url,user_name) VALUES (%s, %s, %s,%s)",
            (user_info["sub"], user_info["email"],user_info["picture"],user_info["name"]),
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
            user_id = session['user']['userinfo'].get('user_id')
            # user_id = 1
            db.modify_db(
                "INSERT INTO images (user_id, title, description, image_url, prompt) VALUES (%s, %s, %s, %s, %s)",
                (user_id, title, description, image_url, prompt),
            )
            return redirect(url_for("user_profile",session=session.get("user")))
    return render_template("upload.html",session=session.get("user"))


def upload_image_to_s3(image):
    s3_client.upload_fileobj(
        image,
        env.get("S3_BUCKET"),
        image.filename,
        ExtraArgs={"ContentType": image.content_type},
    )
    return f"https://{env.get('S3_BUCKET')}.s3.amazonaws.com/{image.filename}"

###############

@app.route('/user/fans')
def show_fans():
    # 直接从请求的查询参数中获取 user_id
    user_id = request.args.get('user_id')

    if not user_id:
        # 如果 URL 中没有 user_id 参数，重定向到登录页面
        return redirect(url_for('login'))

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


    return render_template('follows.html', following=following, followers=followers,session=session.get("user"),)
@app.route('/user/subs')
def show_subscribtion():
    # 直接从请求的查询参数中获取 user_id
    user_id = request.args.get('user_id')

    if not user_id:
        # 如果 URL 中没有 user_id 参数，重定向到登录页面
        return redirect(url_for('login'))

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


    return render_template('subs.html', following=following, followers=followers,session=session.get("user"),)
##############

if __name__ == "__main__":
    app.run(debug=True)
    # app.run(host="0.0.0.0", port=env.get("PORT", 3000))
