"""
Flask-based E-commerce Application
Features: Product Management, Shopping Cart, Checkout System
Created: 2025-12-25
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from datetime import datetime, timedelta
import os
import json

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ecommerce.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

# ==================== Database Models ====================

class Product(db.Model):
    """Product model for e-commerce store"""
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    category = db.Column(db.String(50), nullable=False)
    image_url = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Product {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price': self.price,
            'stock': self.stock,
            'category': self.category,
            'image_url': self.image_url
        }


class User(db.Model):
    """User model for authentication"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<User {self.username}>'


class Order(db.Model):
    """Order model for tracking purchases"""
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, completed, cancelled
    shipping_address = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Order {self.id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'total_amount': self.total_amount,
            'status': self.status,
            'shipping_address': self.shipping_address,
            'created_at': self.created_at.isoformat()
        }


class OrderItem(db.Model):
    """Order items model"""
    __tablename__ = 'order_items'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    
    product = db.relationship('Product', backref='order_items')
    order = db.relationship('Order', backref='items')
    
    def __repr__(self):
        return f'<OrderItem {self.id}>'


# ==================== Helper Functions ====================

def login_required(f):
    """Decorator to check if user is logged in"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def get_cart():
    """Get cart from session"""
    if 'cart' not in session:
        session['cart'] = {}
    return session['cart']


def save_cart(cart):
    """Save cart to session"""
    session['cart'] = cart
    session.modified = True


def calculate_cart_total(cart):
    """Calculate total price of items in cart"""
    total = 0
    for product_id, quantity in cart.items():
        product = Product.query.get(int(product_id))
        if product:
            total += product.price * quantity
    return round(total, 2)


# ==================== Routes - Authentication ====================

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username already exists'}), 400
        
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already exists'}), 400
        
        user = User(username=username, email=email, password=password)
        db.session.add(user)
        db.session.commit()
        
        return jsonify({'message': 'Registration successful'}), 201
    
    return jsonify({'message': 'Send POST request with username, email, password'}), 200


@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        username = data.get('username')
        password = data.get('password')
        
        user = User.query.filter_by(username=username, password=password).first()
        
        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            session.modified = True
            return jsonify({'message': 'Login successful', 'user_id': user.id}), 200
        
        return jsonify({'error': 'Invalid credentials'}), 401
    
    return jsonify({'message': 'Send POST request with username and password'}), 200


@app.route('/logout')
def logout():
    """User logout"""
    session.clear()
    return redirect(url_for('home'))


# ==================== Routes - Products ====================

@app.route('/api/products', methods=['GET', 'POST'])
def products():
    """Get all products or create new product"""
    if request.method == 'GET':
        category = request.args.get('category')
        query = Product.query
        
        if category:
            query = query.filter_by(category=category)
        
        products_list = query.all()
        return jsonify([product.to_dict() for product in products_list]), 200
    
    elif request.method == 'POST':
        data = request.get_json()
        
        # Validate input
        required_fields = ['name', 'price', 'category']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
        
        product = Product(
            name=data['name'],
            description=data.get('description'),
            price=float(data['price']),
            stock=int(data.get('stock', 0)),
            category=data['category'],
            image_url=data.get('image_url')
        )
        
        db.session.add(product)
        db.session.commit()
        
        return jsonify({
            'message': 'Product created successfully',
            'product': product.to_dict()
        }), 201


@app.route('/api/products/<int:product_id>', methods=['GET', 'PUT', 'DELETE'])
def product_detail(product_id):
    """Get, update, or delete a product"""
    product = Product.query.get_or_404(product_id)
    
    if request.method == 'GET':
        return jsonify(product.to_dict()), 200
    
    elif request.method == 'PUT':
        data = request.get_json()
        
        product.name = data.get('name', product.name)
        product.description = data.get('description', product.description)
        product.price = float(data.get('price', product.price))
        product.stock = int(data.get('stock', product.stock))
        product.category = data.get('category', product.category)
        product.image_url = data.get('image_url', product.image_url)
        product.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Product updated successfully',
            'product': product.to_dict()
        }), 200
    
    elif request.method == 'DELETE':
        db.session.delete(product)
        db.session.commit()
        
        return jsonify({'message': 'Product deleted successfully'}), 200


# ==================== Routes - Shopping Cart ====================

@app.route('/api/cart', methods=['GET', 'POST', 'DELETE'])
def cart():
    """Manage shopping cart"""
    if request.method == 'GET':
        cart_items = get_cart()
        cart_data = []
        
        for product_id, quantity in cart_items.items():
            product = Product.query.get(int(product_id))
            if product:
                cart_data.append({
                    'product_id': product_id,
                    'product_name': product.name,
                    'price': product.price,
                    'quantity': quantity,
                    'subtotal': product.price * quantity
                })
        
        total = calculate_cart_total(cart_items)
        
        return jsonify({
            'items': cart_data,
            'total': total,
            'item_count': len(cart_items)
        }), 200
    
    elif request.method == 'POST':
        data = request.get_json()
        product_id = str(data.get('product_id'))
        quantity = int(data.get('quantity', 1))
        
        product = Product.query.get_or_404(int(product_id))
        
        if quantity > product.stock:
            return jsonify({'error': 'Insufficient stock'}), 400
        
        cart_items = get_cart()
        
        if product_id in cart_items:
            cart_items[product_id] += quantity
        else:
            cart_items[product_id] = quantity
        
        save_cart(cart_items)
        
        return jsonify({
            'message': 'Product added to cart',
            'cart': get_cart(),
            'total': calculate_cart_total(cart_items)
        }), 200
    
    elif request.method == 'DELETE':
        product_id = request.args.get('product_id')
        cart_items = get_cart()
        
        if str(product_id) in cart_items:
            del cart_items[str(product_id)]
            save_cart(cart_items)
        
        return jsonify({
            'message': 'Product removed from cart',
            'total': calculate_cart_total(cart_items)
        }), 200


@app.route('/api/cart/update', methods=['PUT'])
def update_cart():
    """Update product quantity in cart"""
    data = request.get_json()
    product_id = str(data.get('product_id'))
    quantity = int(data.get('quantity', 1))
    
    cart_items = get_cart()
    
    if product_id not in cart_items:
        return jsonify({'error': 'Product not in cart'}), 404
    
    if quantity <= 0:
        del cart_items[product_id]
    else:
        product = Product.query.get_or_404(int(product_id))
        if quantity > product.stock:
            return jsonify({'error': 'Insufficient stock'}), 400
        cart_items[product_id] = quantity
    
    save_cart(cart_items)
    
    return jsonify({
        'message': 'Cart updated',
        'total': calculate_cart_total(cart_items)
    }), 200


@app.route('/api/cart/clear', methods=['POST'])
def clear_cart():
    """Clear entire cart"""
    session['cart'] = {}
    session.modified = True
    
    return jsonify({'message': 'Cart cleared'}), 200


# ==================== Routes - Checkout ====================

@app.route('/api/checkout', methods=['POST'])
@login_required
def checkout():
    """Process checkout and create order"""
    data = request.get_json()
    
    cart_items = get_cart()
    
    if not cart_items:
        return jsonify({'error': 'Cart is empty'}), 400
    
    # Validate shipping address
    shipping_address = data.get('shipping_address')
    if not shipping_address:
        return jsonify({'error': 'Shipping address is required'}), 400
    
    # Check stock availability
    for product_id, quantity in cart_items.items():
        product = Product.query.get(int(product_id))
        if not product or quantity > product.stock:
            return jsonify({'error': f'Insufficient stock for product {product_id}'}), 400
    
    # Calculate total
    total_amount = calculate_cart_total(cart_items)
    
    # Create order
    order = Order(
        user_id=session.get('user_id'),
        total_amount=total_amount,
        shipping_address=shipping_address,
        status='completed'
    )
    
    db.session.add(order)
    db.session.flush()
    
    # Create order items and update stock
    for product_id, quantity in cart_items.items():
        product = Product.query.get(int(product_id))
        
        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=quantity,
            price=product.price
        )
        
        product.stock -= quantity
        db.session.add(order_item)
    
    db.session.commit()
    
    # Clear cart
    session['cart'] = {}
    session.modified = True
    
    return jsonify({
        'message': 'Order placed successfully',
        'order': order.to_dict(),
        'items': [{
            'product_id': oi.product_id,
            'product_name': oi.product.name,
            'quantity': oi.quantity,
            'price': oi.price
        } for oi in order.items]
    }), 201


@app.route('/api/orders', methods=['GET'])
@login_required
def get_orders():
    """Get user's orders"""
    user_id = session.get('user_id')
    orders_list = Order.query.filter_by(user_id=user_id).all()
    
    return jsonify([{
        'id': order.id,
        'total_amount': order.total_amount,
        'status': order.status,
        'created_at': order.created_at.isoformat(),
        'items': [{
            'product_name': item.product.name,
            'quantity': item.quantity,
            'price': item.price
        } for item in order.items]
    } for order in orders_list]), 200


@app.route('/api/orders/<int:order_id>', methods=['GET'])
@login_required
def get_order_detail(order_id):
    """Get specific order details"""
    order = Order.query.get_or_404(order_id)
    
    if order.user_id != session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 403
    
    return jsonify({
        'id': order.id,
        'total_amount': order.total_amount,
        'status': order.status,
        'shipping_address': order.shipping_address,
        'created_at': order.created_at.isoformat(),
        'items': [{
            'product_id': item.product_id,
            'product_name': item.product.name,
            'quantity': item.quantity,
            'price': item.price
        } for item in order.items]
    }), 200


# ==================== Routes - Home ====================

@app.route('/')
def home():
    """Home page"""
    return jsonify({
        'message': 'Welcome to Flask E-commerce API',
        'version': '1.0.0',
        'endpoints': {
            'authentication': {
                'register': '/register',
                'login': '/login',
                'logout': '/logout'
            },
            'products': {
                'list_all': 'GET /api/products',
                'create': 'POST /api/products',
                'get_detail': 'GET /api/products/<id>',
                'update': 'PUT /api/products/<id>',
                'delete': 'DELETE /api/products/<id>'
            },
            'cart': {
                'view': 'GET /api/cart',
                'add_item': 'POST /api/cart',
                'update_item': 'PUT /api/cart/update',
                'remove_item': 'DELETE /api/cart?product_id=<id>',
                'clear': 'POST /api/cart/clear'
            },
            'checkout': {
                'checkout': 'POST /api/checkout',
                'orders': 'GET /api/orders',
                'order_detail': 'GET /api/orders/<id>'
            }
        }
    }), 200


# ==================== Error Handlers ====================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Resource not found'}), 404


@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors"""
    return jsonify({'error': 'Internal server error'}), 500


# ==================== Initialize Database ====================

def init_db():
    """Initialize database with sample data"""
    with app.app_context():
        db.create_all()
        
        # Check if products already exist
        if Product.query.first() is None:
            # Add sample products
            sample_products = [
                Product(name='Laptop', description='High-performance laptop', 
                       price=999.99, stock=10, category='Electronics'),
                Product(name='Smartphone', description='Latest smartphone model', 
                       price=699.99, stock=20, category='Electronics'),
                Product(name='Headphones', description='Wireless headphones', 
                       price=199.99, stock=30, category='Electronics'),
                Product(name='T-Shirt', description='Cotton t-shirt', 
                       price=29.99, stock=50, category='Clothing'),
                Product(name='Jeans', description='Denim jeans', 
                       price=79.99, stock=25, category='Clothing'),
                Product(name='Running Shoes', description='Sports running shoes', 
                       price=149.99, stock=15, category='Footwear'),
            ]
            
            for product in sample_products:
                db.session.add(product)
            
            db.session.commit()
            print("Sample products created successfully!")


# ==================== Main ====================

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
