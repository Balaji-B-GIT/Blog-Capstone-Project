import smtplib
from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
import os
import gunicorn
import psycopg2

my_mail = "sampleforpythonmail@gmail.com"
password = os.environ.get("APP_PASSWORD")


'''
Make sure the required packages are installed: 
Open the Terminal in PyCharm (bottom left). 

On Windows type:
python -m pip install -r requirements_3.12.txt

On MacOS type:
pip3 install -r requirements.txt

This will install the packages from the requirements.txt for this project.
'''

app = Flask(__name__)
# If 404 error occurs, change the below secret key
app.config['SECRET_KEY'] = os.environ.get('FLASK_KEY')
ckeditor = CKEditor(app)
Bootstrap5(app)

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

# CREATE DATABASE
class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DB_URI")
db = SQLAlchemy(model_class=Base)
db.init_app(app)

# Gravatar is used for generating random profile pic for users in comments section
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)


@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(Users, user_id)


# python decoration
def admin_only(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if current_user.get_id() != '1':
            return abort(403)
        return func(*args, **kwargs)
    return decorated_function


# CONFIGURE TABLES-----------------------------------------------------------------------------------------
class Users(UserMixin,db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name:Mapped[str] = mapped_column(String(250),nullable=False)
    email:Mapped[str] = mapped_column(String(250),unique=True, nullable=False)
    password:Mapped[str] = mapped_column(Text,nullable=False)
    # This will act like a List of BlogPost objects attached to each User.
    # The "author" refers to the author property in the BlogPost class.
    posts = relationship("BlogPost", back_populates="author")
    # ONE-TO-MANY Relationship between Users and Comment
    comments = relationship("Comment",back_populates="user")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    # Create Foreign Key, "users.id" the users refers to the table name of Users.
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id", ondelete="CASCADE"))
    # Create reference to the Users object. The "posts" refers to the posts property in the User class.
    author = relationship("Users", back_populates="posts")
    # ONE-TO-MANY Relationship between Blogpost and Comment
    comments = relationship("Comment", back_populates="posts",
                            cascade="all, delete-orphan", passive_deletes=True)
    # Above "passive_deletes" tells SQLAlchemy to rely on the database to handle cascading deletes.
    # "cascade" ensures that when a BlogPost is deleted, all related Comment objects will also be deleted.


class Comment(db.Model):
    __tablename__ = "Comments"
    id:Mapped[int] = mapped_column(Integer,primary_key=True)
    # ONE-TO-MANY Relationship with BlogPost
    post_id: Mapped[int] = mapped_column(Integer,db.ForeignKey("blog_posts.id", ondelete="CASCADE"))
    posts = relationship("BlogPost", back_populates="comments")
    # ONE-TO-MANY Relationship with Users
    user_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    user = relationship("Users", back_populates="comments")

    text:Mapped[str] = mapped_column(Text,nullable=False)


with app.app_context():
    db.create_all()
#----------------------------------------------------------------------------------------------------------

@app.route('/register',methods=["POST","GET"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.data.get("email")
        user_exists = db.session.execute(db.select(Users).where(Users.email == email)).scalar()
        if not user_exists:
            name = form.data.get("name")
            password = form.data.get("password")
            hashed_and_salted_password = generate_password_hash(password=password,method='pbkdf2:sha256',salt_length=8)
            new_user = Users(
                name = name,
                email = email,
                password = hashed_and_salted_password
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for("get_all_posts"))
        else:
            flash("User already exists, Please Login!")
            return redirect(url_for("login"))

    return render_template("register.html",register_form = form)


@app.route('/login',methods=["POST","GET"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.data.get("email")
        password = form.data.get("password")
        user_exist = db.session.execute(db.select(Users).where(Users.email == email)).scalar()
        # Shorter way below
        # if user_exist and check_password_hash(user_exist.password,password):
        #     login_user(user_exist)
        #     return redirect(url_for("get_all_posts",logged_in = True))
        # else:
        #     flash("User doesn't exist or Password is in correct")
        if not user_exist:
            flash("User doesn't exist")
        else:
            if check_password_hash(user_exist.password, password):
                login_user(user_exist)
                return redirect(url_for('get_all_posts'))
            else:
                flash("Incorrect password")
    return render_template("login.html",login_form = form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts)


@app.route("/post/<int:post_id>",methods=["POST","GET"])
def show_post(post_id):
    requested_post = db.get_or_404(BlogPost, post_id)
    all_comments = db.session.execute(db.select(Comment).where(Comment.post_id == post_id)).scalars().all()
    if current_user.is_authenticated:
        comments = CommentForm()
        if comments.validate_on_submit():
            comment = request.form.get("comment")
            new_comment = Comment(
                text = comment,
                posts = requested_post,
                user = current_user
            )
            db.session.add(new_comment)
            db.session.commit()
            return redirect(url_for("show_post",post_id=requested_post.id))
        return render_template("post.html", post = requested_post, comment_form = comments, all_comments = all_comments, gravatar = gravatar)
    return render_template("post.html", post=requested_post, all_comments = all_comments, gravatar = gravatar)


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    # Delete comments associated with the post first
    db.session.query(Comment).filter_by(post_id=post_id).delete()
    db.session.commit()
    # Then delete the post
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route('/contact',methods=["POST","GET"])
def contact():
    if request.method == "POST":
        data = request.form
        with smtplib.SMTP("smtp.gmail.com", 587) as connection:
            connection.starttls()
            connection.login(my_mail, password=password)
            connection.sendmail(from_addr=my_mail,
                                to_addrs=my_mail,
                                msg=f"Subject:Message from Blog\n\n"
                                    f"Name : {data['name']}\n"
                                    f"Email : {data['email']}\n"
                                    f"Phone : {data['phone']}\n"
                                    f"Message : {data['message']}")
        flash("Sent Successfully!")
        return render_template("contact.html",submitted = True)
    return render_template("contact.html")


if __name__ == "__main__":
    app.run(debug=True, port=5002)
