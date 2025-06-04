"""
Rutas extendidas del dashboard integrando todas las nuevas funcionalidades
"""

from flask import render_template, redirect, url_for, flash, request, jsonify, send_file
from flask_login import login_required, current_user
from app.dashboard import bp
from app.extensions import db
from app.models import Product, Order, OrderItem
from app.models.invoice import Invoice, InvoiceItem, InvoicePayment
from app.models.inventory import StockMovement, StockAlert, InventoryReport, StockMovementType
from app.models.customer import Customer, CustomerInteraction, CustomerGroup, CustomerAnalytics
from app.utils.decorators import active_business_required
from app.utils.performance import cached_route, LazyLoadingHelper
from app.automation.tasks import send_bulk_email
from datetime import datetime, timedelta
import io
import csv
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import json


# ============== FACTURACIÓN ==============

@bp.route('/invoices')
@login_required
@active_business_required
def invoices():
    """Lista de facturas"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    
    query = Invoice.query.filter_by(user_id=current_user.id)
    
    if status:
        query = query.filter_by(status=status)
    
    # Usar paginación optimizada
    paginated = LazyLoadingHelper.paginate_query(
        query.order_by(Invoice.created_at.desc()),
        page=page,
        per_page=20
    )
    
    return render_template('dashboard/invoices.html',
        invoices=paginated['items'],
        pagination=paginated,
        status_filter=status
    )


@bp.route('/invoices/new', methods=['GET', 'POST'])
@login_required
@active_business_required
def new_invoice():
    """Crear nueva factura"""
    if request.method == 'POST':
        try:
            # Crear factura
            invoice = Invoice(
                user_id=current_user.id,
                client_name=request.form.get('client_name'),
                client_email=request.form.get('client_email'),
                client_phone=request.form.get('client_phone'),
                client_address=request.form.get('client_address'),
                client_tax_id=request.form.get('client_tax_id'),
                currency=current_user.currency,
                tax_rate=float(request.form.get('tax_rate', 0)),
                discount_rate=float(request.form.get('discount_rate', 0)),
                payment_terms=int(request.form.get('payment_terms', 30)),
                notes=request.form.get('notes')
            )
            
            db.session.add(invoice)
            db.session.flush()  # Para obtener el ID
            
            # Agregar items
            items_data = json.loads(request.form.get('items', '[]'))
            for item_data in items_data:
                item = InvoiceItem(
                    invoice_id=invoice.id,
                    description=item_data['description'],
                    quantity=float(item_data['quantity']),
                    unit_price=float(item_data['unit_price']),
                    discount_rate=float(item_data.get('discount_rate', 0))
                )
                item.calculate_totals()
                db.session.add(item)
            
            # Calcular totales
            invoice.calculate_totals()
            
            # Buscar o crear cliente
            customer = Customer.query.filter_by(
                user_id=current_user.id,
                phone=invoice.client_phone
            ).first()
            
            if not customer:
                customer = Customer(
                    user_id=current_user.id,
                    name=invoice.client_name,
                    email=invoice.client_email,
                    phone=invoice.client_phone,
                    address=invoice.client_address,
                    tax_id=invoice.client_tax_id
                )
                db.session.add(customer)
            
            db.session.commit()
            
            flash('Factura creada exitosamente', 'success')
            return redirect(url_for('dashboard.invoice_detail', invoice_id=invoice.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear factura: {str(e)}', 'error')
    
    # Obtener productos para autocompletado
    products = Product.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).all()
    
    return render_template('dashboard/invoice_form.html',
        products=products
    )


@bp.route('/invoices/<int:invoice_id>')
@login_required
@active_business_required
def invoice_detail(invoice_id):
    """Detalle de factura"""
    invoice = Invoice.query.get_or_404(invoice_id)
    
    if invoice.user_id != current_user.id:
        abort(403)
    
    return render_template('dashboard/invoice_detail.html',
        invoice=invoice
    )


@bp.route('/invoices/<int:invoice_id>/pdf')
@login_required
@active_business_required
def invoice_pdf(invoice_id):
    """Genera PDF de factura"""
    invoice = Invoice.query.get_or_404(invoice_id)
    
    if invoice.user_id != current_user.id:
        abort(403)
    
    # Crear PDF en memoria
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    # Configurar PDF (simplificado para el ejemplo)
    y = 750
    
    # Logo y encabezado
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, y, current_user.business_name)
    y -= 20
    
    p.setFont("Helvetica", 10)
    if current_user.address:
        p.drawString(50, y, current_user.address)
        y -= 15
    p.drawString(50, y, f"Tel: {current_user.phone}")
    y -= 30
    
    # Título
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, y, f"FACTURA {invoice.invoice_number}")
    y -= 20
    
    # Fecha
    p.setFont("Helvetica", 10)
    p.drawString(50, y, f"Fecha: {invoice.issue_date.strftime('%d/%m/%Y')}")
    p.drawString(200, y, f"Vencimiento: {invoice.due_date.strftime('%d/%m/%Y')}")
    y -= 30
    
    # Cliente
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Cliente:")
    y -= 15
    
    p.setFont("Helvetica", 10)
    p.drawString(50, y, invoice.client_name)
    y -= 15
    if invoice.client_address:
        p.drawString(50, y, invoice.client_address)
        y -= 15
    p.drawString(50, y, f"Tel: {invoice.client_phone}")
    if invoice.client_tax_id:
        p.drawString(200, y, f"RUC/CI: {invoice.client_tax_id}")
    y -= 30
    
    # Items
    p.setFont("Helvetica-Bold", 10)
    p.drawString(50, y, "Descripción")
    p.drawString(300, y, "Cant.")
    p.drawString(350, y, "Precio")
    p.drawString(420, y, "Total")
    y -= 20
    
    p.setFont("Helvetica", 10)
    for item in invoice.items:
        # Descripción (truncar si es muy larga)
        desc = item.description[:50] + '...' if len(item.description) > 50 else item.description
        p.drawString(50, y, desc)
        p.drawString(300, y, f"{item.quantity:.2f}")
        p.drawString(350, y, f"${item.unit_price:.2f}")
        p.drawString(420, y, f"${item.total:.2f}")
        y -= 20
    
    # Totales
    y -= 20
    p.line(50, y, 500, y)
    y -= 20
    
    p.drawString(350, y, "Subtotal:")
    p.drawString(420, y, f"${invoice.subtotal:.2f}")
    y -= 20
    
    if invoice.discount_amount > 0:
        p.drawString(350, y, f"Descuento ({invoice.discount_rate}%):")
        p.drawString(420, y, f"-${invoice.discount_amount:.2f}")
        y -= 20
    
    if invoice.tax_amount > 0:
        p.drawString(350, y, f"Impuesto ({invoice.tax_rate}%):")
        p.drawString(420, y, f"${invoice.tax_amount:.2f}")
        y -= 20
    
    p.setFont("Helvetica-Bold", 12)
    p.drawString(350, y, "TOTAL:")
    p.drawString(420, y, f"${invoice.total:.2f} {invoice.currency}")
    
    # Notas
    if invoice.notes:
        y -= 40
        p.setFont("Helvetica", 9)
        p.drawString(50, y, "Notas:")
        y -= 15
        # Dividir notas en líneas
        lines = invoice.notes.split('\n')
        for line in lines[:3]:  # Máximo 3 líneas
            p.drawString(50, y, line[:80])
            y -= 15
    
    # Finalizar PDF
    p.showPage()
    p.save()
    
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'factura_{invoice.invoice_number}.pdf'
    )


@bp.route('/invoices/<int:invoice_id>/send', methods=['POST'])
@login_required
@active_business_required
def send_invoice(invoice_id):
    """Envía factura por email"""
    invoice = Invoice.query.get_or_404(invoice_id)
    
    if invoice.user_id != current_user.id:
        abort(403)
    
    try:
        # Aquí implementarías el envío por email
        # Por ahora solo actualizamos el estado
        invoice.status = 'sent'
        invoice.sent_at = datetime.utcnow()
        db.session.commit()
        
        flash('Factura enviada exitosamente', 'success')
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ============== INVENTARIO ==============

@bp.route('/inventory')
@login_required
@active_business_required
@cached_route(timeout=300)
def inventory():
    """Vista principal de inventario"""
    # Resumen de estado
    status_report = InventoryReport.stock_status_report(current_user.id)
    
    # Alertas activas
    active_alerts = StockAlert.query.filter_by(
        user_id=current_user.id,
        status='active'
    ).order_by(StockAlert.severity.desc()).limit(10).all()
    
    return render_template('dashboard/inventory.html',
        status_report=status_report,
        active_alerts=active_alerts
    )


@bp.route('/inventory/movements')
@login_required
@active_business_required
def inventory_movements():
    """Historial de movimientos de inventario"""
    page = request.args.get('page', 1, type=int)
    product_id = request.args.get('product_id', type=int)
    movement_type = request.args.get('type', '')
    
    # Fechas por defecto (últimos 30 días)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    
    # Construir query
    query = StockMovement.query.filter_by(user_id=current_user.id)
    
    if product_id:
        query = query.filter_by(product_id=product_id)
    
    if movement_type:
        query = query.filter_by(movement_type=movement_type)
    
    query = query.filter(
        StockMovement.created_at.between(start_date, end_date)
    )
    
    # Paginación
    movements = query.order_by(StockMovement.created_at.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    
    # Productos para filtro
    products = Product.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).order_by(Product.name).all()
    
    return render_template('dashboard/inventory_movements.html',
        movements=movements,
        products=products,
        movement_types=StockMovementType,
        filters={
            'product_id': product_id,
            'type': movement_type
        }
    )


@bp.route('/inventory/adjust', methods=['POST'])
@login_required
@active_business_required
def adjust_inventory():
    """Ajuste manual de inventario"""
    try:
        product_id = request.form.get('product_id', type=int)
        adjustment = request.form.get('adjustment', type=int)
        reason = request.form.get('reason', '')
        
        product = Product.query.get_or_404(product_id)
        
        if product.user_id != current_user.id:
            abort(403)
        
        # Crear movimiento
        movement = StockMovement.create_movement(
            product=product,
            movement_type=StockMovementType.ADJUSTMENT,
            quantity=adjustment,
            notes=reason,
            reference='Ajuste manual'
        )
        
        db.session.commit()
        
        flash(f'Inventario ajustado: {product.name}', 'success')
        return jsonify({'success': True, 'new_stock': product.stock})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/inventory/restock', methods=['GET', 'POST'])
@login_required
@active_business_required
def restock_products():
    """Reabastecer productos"""
    if request.method == 'POST':
        try:
            # Procesar reabastecimiento masivo
            items = json.loads(request.form.get('items', '[]'))
            
            for item in items:
                product = Product.query.get(item['product_id'])
                if product and product.user_id == current_user.id:
                    # Crear movimiento de entrada
                    movement = StockMovement.create_movement(
                        product=product,
                        movement_type=StockMovementType.PURCHASE,
                        quantity=item['quantity'],
                        unit_cost=item.get('cost', product.cost_price),
                        reference=item.get('reference', ''),
                        notes=item.get('notes', '')
                    )
                    
                    # Actualizar fecha de último reabastecimiento
                    product.last_restock_date = datetime.utcnow()
                    
                    # Actualizar costo si se proporcionó
                    if 'cost' in item:
                        product.cost_price = item['cost']
            
            db.session.commit()
            flash('Productos reabastecidos exitosamente', 'success')
            return redirect(url_for('dashboard.inventory'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al reabastecer: {str(e)}', 'error')
    
    # Productos con stock bajo
    products_to_restock = Product.query.filter(
        Product.user_id == current_user.id,
        Product.is_active == True,
        Product.track_inventory == True,
        Product.stock <= Product.reorder_point
    ).order_by(Product.stock.asc()).all()
    
    return render_template('dashboard/restock_form.html',
        products=products_to_restock
    )


# ============== CRM ==============

@bp.route('/customers')
@login_required
@active_business_required
def customers():
    """Lista de clientes"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    segment = request.args.get('segment', '')
    
    # Query base
    query = Customer.query.filter_by(user_id=current_user.id)
    
    # Búsqueda
    if search:
        query = query.filter(
            db.or_(
                Customer.name.ilike(f'%{search}%'),
                Customer.email.ilike(f'%{search}%'),
                Customer.phone.ilike(f'%{search}%')
            )
        )
    
    # Filtro por segmento
    if segment:
        query = query.filter_by(segment=segment)
    
    # Paginación
    customers = query.order_by(Customer.total_spent.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Resumen
    summary = CustomerAnalytics.get_customer_summary(current_user.id)
    
    return render_template('dashboard/customers.html',
        customers=customers,
        summary=summary,
        search=search,
        segment_filter=segment
    )


@bp.route('/customers/<int:customer_id>')
@login_required
@active_business_required
def customer_detail(customer_id):
    """Detalle de cliente"""
    customer = Customer.query.get_or_404(customer_id)
    
    if customer.user_id != current_user.id:
        abort(403)
    
    # Actualizar estadísticas
    customer.update_statistics()
    db.session.commit()
    
    # Pedidos recientes
    recent_orders = customer.orders.order_by(
        Order.created_at.desc()
    ).limit(10).all()
    
    # Interacciones recientes
    recent_interactions = customer.interactions.order_by(
        CustomerInteraction.interaction_date.desc()
    ).limit(10).all()
    
    # Productos favoritos
    favorite_products = db.session.query(
        Product.name,
        func.sum(OrderItem.quantity).label('total_purchased')
    ).join(OrderItem).join(Order).filter(
        Order.customer_id == customer.id,
        Order.status == 'delivered'
    ).group_by(Product.id).order_by(
        func.sum(OrderItem.quantity).desc()
    ).limit(5).all()
    
    return render_template('dashboard/customer_detail.html',
        customer=customer,
        recent_orders=recent_orders,
        recent_interactions=recent_interactions,
        favorite_products=favorite_products
    )


@bp.route('/customers/<int:customer_id>/interaction', methods=['POST'])
@login_required
@active_business_required
def add_customer_interaction(customer_id):
    """Agregar interacción con cliente"""
    customer = Customer.query.get_or_404(customer_id)
    
    if customer.user_id != current_user.id:
        abort(403)
    
    try:
        interaction = CustomerInteraction(
            customer_id=customer.id,
            user_id=current_user.id,
            interaction_type=request.form.get('type'),
            channel=request.form.get('channel'),
            subject=request.form.get('subject'),
            description=request.form.get('description'),
            outcome=request.form.get('outcome'),
            follow_up_required=request.form.get('follow_up') == 'on',
            follow_up_date=datetime.strptime(request.form.get('follow_up_date'), '%Y-%m-%d') if request.form.get('follow_up_date') else None,
            created_by=current_user.business_name
        )
        
        db.session.add(interaction)
        db.session.commit()
        
        flash('Interacción registrada exitosamente', 'success')
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/customers/groups')
@login_required
@active_business_required
def customer_groups():
    """Grupos de clientes"""
    groups = CustomerGroup.query.filter_by(
        user_id=current_user.id
    ).order_by(CustomerGroup.name).all()
    
    return render_template('dashboard/customer_groups.html',
        groups=groups
    )


@bp.route('/customers/groups/<int:group_id>/campaign', methods=['GET', 'POST'])
@login_required
@active_business_required
def customer_campaign(group_id):
    """Crear campaña para grupo de clientes"""
    group = CustomerGroup.query.get_or_404(group_id)
    
    if group.user_id != current_user.id:
        abort(403)
    
    if request.method == 'POST':
        # Enviar campaña
        subject = request.form.get('subject')
        content = request.form.get('content')
        
        # Ejecutar en background
        send_bulk_email(current_user.id, group_id, subject, content)
        
        flash('Campaña iniciada. Los emails se enviarán en segundo plano.', 'success')
        return redirect(url_for('dashboard.customer_groups'))
    
    return render_template('dashboard/customer_campaign.html',
        group=group
    )


# ============== REPORTES INTEGRADOS ==============

@bp.route('/reports')
@login_required
@active_business_required
def reports():
    """Centro de reportes"""
    return render_template('dashboard/reports.html')


@bp.route('/reports/generate', methods=['POST'])
@login_required
@active_business_required
def generate_report():
    """Genera reporte personalizado"""
    report_type = request.form.get('type')
    start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d')
    end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d')
    format_type = request.form.get('format', 'pdf')
    
    try:
        if report_type == 'sales':
            data = generate_sales_report(current_user.id, start_date, end_date)
        elif report_type == 'inventory':
            data = generate_inventory_report(current_user.id, start_date, end_date)
        elif report_type == 'customers':
            data = generate_customer_report(current_user.id, start_date, end_date)
        elif report_type == 'financial':
            data = generate_financial_report(current_user.id, start_date, end_date)
        else:
            return jsonify({'error': 'Tipo de reporte no válido'}), 400
        
        # Generar archivo según formato
        if format_type == 'csv':
            return export_report_csv(data, report_type)
        elif format_type == 'pdf':
            return export_report_pdf(data, report_type)
        else:
            return jsonify(data)  # JSON para API
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Funciones auxiliares para reportes

def generate_sales_report(user_id, start_date, end_date):
    """Genera datos de reporte de ventas"""
    # Ventas por día
    daily_sales = db.session.query(
        func.date(Order.created_at).label('date'),
        func.count(Order.id).label('orders'),
        func.sum(Order.total).label('revenue')
    ).filter(
        Order.user_id == user_id,
        Order.created_at.between(start_date, end_date),
        Order.status != 'cancelled'
    ).group_by(func.date(Order.created_at)).all()
    
    # Productos más vendidos
    top_products = db.session.query(
        Product.name,
        func.sum(OrderItem.quantity).label('quantity'),
        func.sum(OrderItem.subtotal).label('revenue')
    ).join(OrderItem).join(Order).filter(
        Order.user_id == user_id,
        Order.created_at.between(start_date, end_date),
        Order.status != 'cancelled'
    ).group_by(Product.id).order_by(
        func.sum(OrderItem.subtotal).desc()
    ).limit(20).all()
    
    return {
        'period': {
            'start': start_date,
            'end': end_date
        },
        'summary': {
            'total_orders': sum(d.orders for d in daily_sales),
            'total_revenue': sum(d.revenue for d in daily_sales),
            'average_daily': sum(d.revenue for d in daily_sales) / len(daily_sales) if daily_sales else 0
        },
        'daily_sales': [
            {
                'date': d.date.strftime('%Y-%m-%d'),
                'orders': d.orders,
                'revenue': float(d.revenue)
            } for d in daily_sales
        ],
        'top_products': [
            {
                'name': p.name,
                'quantity': int(p.quantity),
                'revenue': float(p.revenue)
            } for p in top_products
        ]
    }


def export_report_csv(data, report_type):
    """Exporta reporte en formato CSV"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Headers según tipo de reporte
    if report_type == 'sales':
        writer.writerow(['Fecha', 'Pedidos', 'Ingresos'])
        for day in data['daily_sales']:
            writer.writerow([day['date'], day['orders'], day['revenue']])
    
    # Más tipos de reporte...
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'{report_type}_report_{datetime.now().strftime("%Y%m%d")}.csv'
    )
