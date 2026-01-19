import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from datetime import datetime
import random
from sqlalchemy import text
import json
import services.housing as housing_service
import services.gemini as gemini_service

load_dotenv()

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///finance.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ------------------ MODELS ------------------

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True)
    type = db.Column(db.String(20))  # expense / income
    is_need = db.Column(db.Boolean, default=True)
    

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100))
    amount = db.Column(db.Float)
    date = db.Column(db.DateTime, default=datetime.utcnow)

class Income(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100))
    amount = db.Column(db.Float)
    date = db.Column(db.DateTime, default=datetime.utcnow)

class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100), unique=True)
    limit = db.Column(db.Float)


class UserDetails(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(200), nullable=True)
    radius = db.Column(db.Integer, nullable=True)
    insurance_type = db.Column(db.String(100), nullable=True)
    family_members = db.Column(db.Text, nullable=True)  # JSON list of {name, age, relation}
    pets = db.Column(db.Text, nullable=True)  # JSON list of {type, count, ages}

# ------------------ DEFAULT CATEGORIES ------------------

def insert_default_categories():
    defaults = [
        ("Rent", "expense", True),
        ("Food", "expense", True),
        ("Utilities", "expense", True),
        ("Transport", "expense", True),
        ("Entertainment", "expense", False),
        ("Salary", "income", True),
        ("Side Hustle", "income", False),
    ]

    for name, type_, is_need in defaults:
        exists = Category.query.filter_by(name=name).first()
        if not exists:
            db.session.add(Category(name=name, type=type_, is_need=is_need))
    db.session.commit()


def random_color():
    # return a random HEX color that's not too light
    while True:
        c = '#%06x' % random.randint(0, 0xFFFFFF)
        try:
            r = int(c[1:3], 16)
            g = int(c[3:5], 16)
            b = int(c[5:7], 16)
        except Exception:
            return c
        if (r + g + b) / 3 < 230:
            return c
    

# ------------------ DASHBOARD ------------------

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if "expense_amount" in request.form:
            db.session.add(
                Expense(
                    category=request.form["expense_category"],
                    amount=float(request.form["expense_amount"]),
                )
            )
            db.session.commit()
            return redirect(url_for("index", tab="transactions"))
        elif "income_amount" in request.form:
            db.session.add(
                Income(
                    category=request.form["income_category"],
                    amount=float(request.form["income_amount"]),
                )
            )
            db.session.commit()
            return redirect(url_for("index", tab="transactions"))

    expenses = Expense.query.order_by(Expense.date.desc()).all()
    income = Income.query.order_by(Income.date.desc()).all()

    expense_categories = Category.query.filter_by(type="expense").all()
    income_categories = Category.query.filter_by(type="income").all()

    # Totals for charts
    expense_totals = {}
    for e in expenses:
        expense_totals[e.category] = expense_totals.get(e.category, 0) + e.amount

    income_totals = {}
    for i in income:
        income_totals[i.category] = income_totals.get(i.category, 0) + i.amount

    budgets = {b.category: b.limit for b in Budget.query.all()}

    # Build color arrays for charts based on Category.color
    def colors_for_labels(labels):
        # generate a color per label (deterministic from name for stability)
        cols = []
        for lbl in labels:
            # deterministic pseudo-random color based on name hash
            h = abs(hash(lbl))
            r = (h & 0xFF0000) >> 16
            g = (h & 0x00FF00) >> 8
            b = (h & 0x0000FF)
            # make sure not too light
            avg = (r + g + b) / 3
            if avg > 220:
                r = r // 2; g = g // 2; b = b // 2
            cols.append('#%02x%02x%02x' % (r, g, b))
        return cols

    expense_labels = list(expense_totals.keys())
    income_labels = list(income_totals.keys())
    expense_colors = colors_for_labels(expense_labels) if expense_labels else []
    income_colors = colors_for_labels(income_labels) if income_labels else []
    budget_labels = list(budgets.keys())
    budget_colors = colors_for_labels(budget_labels) if budget_labels else []

    # determine which tab should be active on render
    active_tab = request.args.get("tab", "dashboard")

    # build details object from UserDetails table so the full index page can render the tab
    ud = UserDetails.query.first()
    details = None
    if ud:
        try:
            fm = json.loads(ud.family_members) if ud.family_members else []
        except Exception:
            fm = []
        try:
            pets = json.loads(ud.pets) if ud.pets else []
        except Exception:
            pets = []
        details = type('X', (), {})()
        details.location = ud.location
        details.radius = ud.radius
        details.insurance_type = ud.insurance_type
        details.family_members = fm
        details.pets = pets

    return render_template(
        "index.html",
        expenses=expenses,
        income=income,
        incomes=income,
        expense_categories=expense_categories,
        income_categories=income_categories,
        expense_totals=expense_totals,
        income_totals=income_totals,
        budgets=budgets,
        budgets_list=Budget.query.all(),
        chartExpenseColors=expense_colors,
        chartIncomeColors=income_colors,
        budget_colors=budget_colors,
        active_tab=active_tab,
        details=details
    )


# ------------------ BUDGET CRUD ------------------


@app.route("/add-budget", methods=["POST"])
def add_budget():
    category = request.form.get("budget_category")
    limit = request.form.get("budget_limit")
    if not category or not limit:
        return redirect(url_for("index"))

    try:
        limit_val = float(limit)
    except ValueError:
        return redirect(url_for("index"))

    b = Budget.query.filter_by(category=category).first()
    if b:
        b.limit = limit_val
    else:
        db.session.add(Budget(category=category, limit=limit_val))
    db.session.commit()
    return redirect(url_for("index", tab="budget"))


@app.route('/add-category', methods=['POST'])
def add_category():
    name = request.form.get('category_name')
    type_ = request.form.get('category_type')
    is_need = True if request.form.get('is_need') == 'on' else False
    if not name or not type_:
        return redirect(url_for('index', tab='dashboard'))
    if Category.query.filter_by(name=name).first():
        return redirect(url_for('index', tab='dashboard'))
    c = Category(name=name, type=type_, is_need=is_need)
    db.session.add(c)
    db.session.commit()
    return redirect(url_for('index', tab='dashboard'))


@app.route('/delete-category/<int:id>', methods=['POST'])
def delete_category(id):
    c = Category.query.get_or_404(id)
    name = c.name
    # delete any dependent rows that reference this category name
    try:
        Expense.query.filter_by(category=name).delete()
        Income.query.filter_by(category=name).delete()
        Budget.query.filter_by(category=name).delete()
    except Exception:
        # fallback: remove via session for safety
        for e in Expense.query.filter_by(category=name).all():
            db.session.delete(e)
        for i in Income.query.filter_by(category=name).all():
            db.session.delete(i)
        for b in Budget.query.filter_by(category=name).all():
            db.session.delete(b)
    # finally remove the category itself
    db.session.delete(c)
    db.session.commit()
    return redirect(url_for('index', tab='dashboard'))


@app.route("/delete-budget/<int:id>", methods=["POST", "GET"])
def delete_budget(id):
    b = Budget.query.get_or_404(id)
    db.session.delete(b)
    db.session.commit()
    return redirect(url_for("index", tab="budget"))

# ------------------ DELETE TRANSACTION ------------------

@app.route("/delete-transaction/<txn_type>/<int:id>", methods=['GET', 'POST'])
def delete_transaction(txn_type, id):
    txn = Expense.query.get_or_404(id) if txn_type == "expense" else Income.query.get_or_404(id)
    db.session.delete(txn)
    db.session.commit()
    return redirect(url_for("index", tab="transactions"))

# ------------------ AI ADVISOR ------------------

@app.route("/ai-advisor", methods=["POST"])
def ai_advisor():
    expenses = Expense.query.all()
    totals = {}

    for e in expenses:
        totals[e.category] = totals.get(e.category, 0) + e.amount

    advice = [
        f"Reduce {cat} by 10% → save ${total * 0.1:.2f}/month"
        for cat, total in totals.items()
        if total > 500
    ]

    if not advice:
        advice = ["Your spending looks healthy 👍"]

    return render_template("tabs/ai_advisor.html", advice=advice)


@app.route('/api/housing-search', methods=['POST'])
def housing_search_api():
    # Expects JSON POST with: location, radius, min_beds, min_baths, min_sqft
    data = request.get_json() or {}
    location = data.get('location')
    radius = data.get('radius')
    min_beds = int(data.get('min_beds', 1) or 1)
    min_baths = int(data.get('min_baths', 1) or 1)
    min_sqft = int(data.get('min_sqft', 300) or 300)

    try:
        results = housing_service.search_housing(
            location=location,
            radius=radius,
            min_beds=min_beds,
            min_baths=min_baths,
            min_sqft=min_sqft,
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    return jsonify({'results': results})


@app.route('/api/ai-recommend', methods=['POST'])
def api_ai_recommend():
    # Build user details, budgets, and expenses
    ud = UserDetails.query.first()
    if not ud:
        return jsonify({'error': 'No user details found. Please fill User Details tab.'}), 400

    try:
        family = json.loads(ud.family_members) if ud.family_members else []
        pets = json.loads(ud.pets) if ud.pets else []
    except Exception:
        family = []
        pets = []

    # Simple heuristic to compute minimum needs
    total_people = len(family) if family else 1
    children = sum(1 for m in family if (('relation' in m and 'child' in str(m.get('relation','')).lower()) or (isinstance(m.get('age'), int) and m.get('age') < 18)))
    adults = total_people - children
    pets_count = sum(int(p.get('count', 0)) for p in pets)

    min_beds = max(1, (total_people + 1) // 2)
    min_baths = max(1, (total_people + 1) // 3)
    min_sqft = 300 + total_people * 200 + pets_count * 50

    needs = {'beds': min_beds, 'baths': min_baths, 'sqft': min_sqft}

    # Find cheapest listing meeting criteria
    location = ud.location
    radius = ud.radius
    listings = housing_service.search_housing(location=location, radius=radius, min_beds=min_beds, min_baths=min_baths, min_sqft=min_sqft, max_results=20)
    # filter usable listings
    candidates = [l for l in listings if (l.get('beds') is None or int(l.get('beds') or 0) >= min_beds) and (l.get('sqft') is None or int(l.get('sqft') or 0) >= min_sqft)]
    # parse price safely
    def price_of(it):
        try:
            return float(it.get('price') or 0)
        except Exception:
            return 0
    if candidates:
        candidates.sort(key=price_of)
        best = candidates[0]
    else:
        best = listings[0] if listings else None

    # Build suggested budgets: update Rent to listing price, and compute basic minima for food/utilities/transport
    current_budgets = {b.category: b.limit for b in Budget.query.all()}
    suggested = {}
    if best and price_of(best) > 0:
        suggested['Rent'] = price_of(best)
    # basic per-person food baseline
    food_per_person = 200
    if 'Food' in current_budgets:
        suggested['Food'] = max(current_budgets.get('Food', 0) * 0.5, food_per_person * total_people)
    if 'Utilities' in current_budgets:
        suggested['Utilities'] = max(50, 0.12 * min_sqft)
    if 'Transport' in current_budgets:
        suggested['Transport'] = max(50, 50 * total_people)

    # Ensure numeric values
    for k in list(suggested.keys()):
        try:
            suggested[k] = float(suggested[k])
        except Exception:
            suggested[k] = 0.0

    # Compose explanation via Gemini when available
    details_obj = {'location': ud.location, 'radius': ud.radius, 'family': family, 'pets': pets}
    explanation = gemini_service.compose_explanation(needs, best, suggested, details_obj)

    return jsonify({
        'needs': needs,
        'best_listing': best,
        'suggested_budgets': suggested,
        'explanation': explanation
    })


@app.route('/api/apply-budget-updates', methods=['POST'])
def api_apply_budget_updates():
    data = request.get_json() or {}
    updates = data.get('updates') or {}
    if not updates:
        return jsonify({'success': False, 'error': 'No updates provided.'}), 400
    try:
        for cat, val in updates.items():
            try:
                valf = float(val)
            except Exception:
                valf = 0.0
            b = Budget.query.filter_by(category=cat).first()
            if b:
                b.limit = valf
            else:
                db.session.add(Budget(category=cat, limit=valf))
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/user-details', methods=['GET', 'POST'])
def user_details():
    # Save POST then redirect back to index(tab=user-details); GET redirects to index too
    if request.method == 'POST':
        ud = UserDetails.query.first()
        location = request.form.get('location')
        radius = request.form.get('radius')
        insurance_type = request.form.get('insurance_type')
        family_members = request.form.get('family_members')
        pets = request.form.get('pets')
        if not ud:
            ud = UserDetails()
            db.session.add(ud)
        ud.location = location
        try:
            ud.radius = int(radius) if radius else None
        except Exception:
            ud.radius = None
        ud.insurance_type = insurance_type
        ud.family_members = family_members if family_members else '[]'
        ud.pets = pets if pets else '[]'
        db.session.commit()
        return redirect(url_for('index', tab='user-details'))

    return redirect(url_for('index', tab='user-details'))

# ------------------ INIT ------------------

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        insert_default_categories()
    app.run(debug=True)
