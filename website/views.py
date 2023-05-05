from library.utils import get_accounts_from_token
from visualization.visualize import visualize

from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from . import db
from .models import User

views = Blueprint('views', __name__)


@views.route('/', methods=['GET', 'POST'])
@login_required
def home():
    user = db.session.query(User).filter_by(id=current_user.id).first()

    # User already entered both token and account_id
    if user.token != '' and user.account_id != '':
        return redirect(url_for('views.visualization'))

    # User is ready to enter token or account_id
    if request.method != 'POST':
        if user.token == '':
            return render_template("enter_token.html", user=current_user)
        else:
            print(get_accounts_from_token(user.token))
            return render_template("enter_account_id.html", user=current_user, accounts=get_accounts_from_token(user.token))

    # User have just entered token or account_id
    token = request.form.get('token')  # Gets the note from the HTML
    account_id = request.form.get('account_id')
    if token is not None:
        accounts = get_accounts_from_token(token)
        if accounts is None:
            flash('Token is incorrect! (Authentication error)', category='error')
            return render_template("enter_token.html", user=current_user)
        else:
            user.token = token
            db.session.commit()
            flash('Token was successfully saved! (Authentication success)', category='success')
            if len(accounts) != 1:
                return render_template("enter_account_id.html", user=current_user, accounts=accounts)
    user.account_id = account_id
    db.session.commit()
    flash('account_id was successfully saved!', category='success')
    return redirect(url_for('views.visualization'))


@views.route('/visualization', methods=['GET', 'POST'])
@login_required
def visualization():
    # TODO: make visualization
    user = db.session.query(User).filter_by(id=current_user.id).first()
    if user.token == '' or user.account_id == '':
        return redirect(url_for('views.home'))
    
    graph = visualize(user.token, user.account_id)
    return render_template("visualization.html", user=current_user, graph=graph)
