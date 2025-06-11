"""
Rutas extendidas del Dashboard para funcionalidades avanzadas
Incluye facturación, inventario, CRM y analytics
"""
from flask import render_template, redirect, url_for, flash, request, jsonify, send_file
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from decimal import Decimal
import json
import csv
import io
from app import db
from app.dashboard import bp
from app.dashboard.analytics import Analytics
from app.models import Product, Order
from app.models.invoice import Invoice, InvoiceSeries, InvoiceItem, InvoicePayment, RecurringInvoice
from app.models.inventory import Warehouse, StockItem, InventoryMovement, StockAlert, PurchaseOrder
from app.models.customer import Customer, CustomerGroup, CustomerInteraction, MarketingCampaign
from app.utils.decorators import business_required, active_business_required

# ==================== ANALYTICS ROUTES ====================

@bp.route('/analytics')
@login_required
@active_business_required
def analytics():
    """Dashboard de analytics"""
    analytics = Analytics(current_user.id)
    
    # Obtener rango de fechas de la query
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    if date_from:
        date_from = datetime.strptime(date_from, '%Y-%m-%d')
    else:
        date_from = datetime.utcnow() - timedelta(days=30)
    
    if date_to:
        date_to = datetime.strptime(date_to, '%Y-%m-%d')
    else:
        date_to = datetime.utcnow()
    
    # Obtener métricas
    metrics = analytics.get_dashboard_metrics(date_from, date_to)
    sales_trend = analytics.get_sales_trend()
    top_products = analytics.get_top_products()
    customer_analytics = analytics.get_customer_analytics()
    hourly_sales = analytics.get_sales_by_hour()
    
    return render_template('dashboard/analytics.html',
        metrics=metrics,
        sales_trend=sales_trend,
        top_products=top_products,
        customer_analytics=customer_analytics,
        hourly_sales=hourly_sales,
        date_from=date_from,
        date_to=date_to
    )

@bp.route('/analytics/api/metrics')
@login_required
@active_business_required
def analytics_api_metrics():
    """API para obtener métricas en tiempo real"""
    analytics = Analytics(current_user.id)
    metric_type = request.args.get('type', 'dashboard')
    
    if metric_type == 'dashboard':
        data = analytics.get_dashboard_metrics()
    elif metric_type == 'sales_trend':
        period = request.args.get('period', 'daily')
        days = request.args.get('days', 30, type=int)
        data = analytics.get_sales_trend(period, days)
    elif metric_type == 'predictive':
        data = analytics.get_predictive_analytics()
    else:
        data = {'error': 'Invalid metric type'}
    
    return jsonify(data)

@bp.route('/analytics/export')
@login_required
@active_business_required
def export_analytics():
    """Exportar datos de analytics"""
    analytics = Analytics(current_user.id)
    report_type = request.args.get('type', 'full')
    format_type = request.args.get('format', 'json')
    
    data = analytics.export_analytics_data(report_type)
    
    if format_type == 'json':
        return jsonify(data)
    elif format_type == 'csv':
        # Convertir a CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Escribir headers y datos según el tipo de reporte
        if 'dashboard_metrics' in data:
            writer.writerow(['Métrica', 'Valor'])
            for key, value in data['dashboard_metrics'].items():
                if not isinstance(value, dict):
                    writer.writerow([key, value])
        
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode()),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'analytics_{report_type}_{datetime.utcnow().strftime("%Y%m%d")}.csv'
        )

# ==================== INVOICE ROUTES ====================

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
    
    invoices = query.order_by(Invoice.created_at.desc())\
        .paginate(page=page, per_page=20, error_out=False)
    
    # Estadísticas
    total_pending = Invoice.query.filter_by(
        user_id=current_user.id,
        status='issued'
    ).count()
    
    total_overdue = Invoice.query.filter(
        Invoice.user_id == current_user.id,
        Invoice.status != 'paid',
        Invoice.due_date < datetime.utcnow()
    ).count()
    
    return render_template('dashboard/invoices.html',
        invoices=invoices,
        status_filter=status,
        total_pending=total_pending,
        total_overdue=total_overdue
    )

@bp.route('/invoices/new', methods=['GET', 'POST'])
@login_required
@active_business_required
def new_invoice():
    """Crear nueva factura"""
    if request.method == 'POST':
        # Obtener o crear serie
        series = InvoiceSeries.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).first()
        
        if not series:
            series = InvoiceSeries(
                user_id=current_user.id,
                prefix='FAC'
            )
            db.session.add(series)
            db.session.flush()
        
        # Crear factura
        invoice = Invoice(
            user_id=current_user.id,
            series_id=series.id,
            invoice_number=series.get_next_number(),
            customer_name=request.form.get('customer_name'),
            customer_tax_id=request.form.get('customer_tax_id'),
            customer_address=request.form.get('customer_address'),
            customer_email=request.form.get('customer_email'),
            customer_phone=request.form.get('customer_phone'),
            tax_rate=Decimal(request.form.get('tax_rate', 0)),
            notes=request.form.get('notes')
        )
        
        # Agregar items
        items = json.loads(request.form.get('items', '[]'))
        for item_data in items:
            item = InvoiceItem(
                description=item_data['description'],
                quantity=Decimal(item_data['quantity']),
                unit_price=Decimal(item_data['unit_price']),
                discount_rate=Decimal(item_data.get('discount_rate', 0))
            )
            item.calculate_subtotal()
            invoice.items.append(item)
        
        invoice.calculate_totals()
        
        # Si se marca como emitida
        if request.form.get('issue_now') == 'true':
            invoice.status = 'issued'
            invoice.issued_at = datetime.utcnow()
        
        db.session.add(invoice)
        db.session.commit()
        
        flash(f'Factura {invoice.invoice_number} creada exitosamente', 'success')
        return redirect(url_for('dashboard.invoice_detail', invoice_id=invoice.id))
    
    # GET - Mostrar formulario
    customers = Customer.query.filter_by(user_id=current_user.id).all()
    products = Product.query.filter_by(user_id=current_user.id, is_active=True).all()
    
    return render_template('dashboard/invoice_form.html',
        customers=customers,
        products=products,
        invoice=None
    )

@bp.route('/invoices/<int:invoice_id>')
@login_required
@active_business_required
def invoice_detail(invoice_id):
    """Detalle de factura"""
    invoice = Invoice.query.get_or_404(invoice_id)
    
    if invoice.user_id != current_user.id:
        flash('No tienes permiso para ver esta factura', 'danger')
        return redirect(url_for('dashboard.invoices'))
    
    return render_template('dashboard/invoice_detail.html', invoice=invoice)

@bp.route('/invoices/<int:invoice_id>/payment', methods=['POST'])
@login_required
@active_business_required
def add_invoice_payment(invoice_id):
    """Registrar pago de factura"""
    invoice = Invoice.query.get_or_404(invoice_id)
    
    if invoice.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'No autorizado'}), 403
    
    payment = InvoicePayment(
        invoice_id=invoice.id,
        amount=Decimal(request.json.get('amount')),
        payment_method=request.json.get('payment_method'),
        reference=request.json.get('reference'),
        notes=request.json.get('notes')
    )
    
    db.session.add(payment)
    
    # Actualizar estado si está totalmente pagada
    if invoice.get_pending_amount() <= payment.amount:
        invoice.mark_as_paid()
    elif invoice.status == 'issued':
        invoice.status = 'partial'
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Pago registrado exitosamente',
        'pending_amount': float(invoice.get_pending_amount())
    })

# ==================== INVENTORY ROUTES ====================

@bp.route('/inventory')
@login_required
@active_business_required
def inventory():
    """Gestión de inventario"""
    page = request.args.get('page', 1, type=int)
    warehouse_id = request.args.get('warehouse', type=int)
    low_stock_only = request.args.get('low_stock') == 'true'
    
    # Obtener almacenes
    warehouses = Warehouse.query.filter_by(user_id=current_user.id).all()
    
    # Si no hay almacenes, crear uno por defecto
    if not warehouses:
        default_warehouse = Warehouse(
            user_id=current_user.id,
            name='Almacén Principal',
            code='MAIN',
            is_default=True
        )
        db.session.add(default_warehouse)
        db.session.commit()
        warehouses = [default_warehouse]
    
    # Query de stock
    query = db.session.query(
        StockItem, Product
    ).join(
        Product, Product.id == StockItem.product_id
    ).filter(
        Product.user_id == current_user.id
    )
    
    if warehouse_id:
        query = query.filter(StockItem.warehouse_id == warehouse_id)
    
    if low_stock_only:
        query = query.filter(
            StockItem.quantity <= StockItem.min_stock
        )
    
    stock_items = query.paginate(page=page, per_page=20, error_out=False)
    
    # Alertas activas
    active_alerts = StockAlert.query.filter_by(
        user_id=current_user.id,
        is_resolved=False
    ).count()
    
    return render_template('dashboard/inventory.html',
        stock_items=stock_items,
        warehouses=warehouses,
        selected_warehouse=warehouse_id,
        low_stock_only=low_stock_only,
        active_alerts=active_alerts
    )

@bp.route('/inventory/movement', methods=['POST'])
@login_required
@active_business_required
def create_inventory_movement():
    """Crear movimiento de inventario"""
    try:
        movement = InventoryMovement(
            user_id=current_user.id,
            created_by=current_user.id,
            movement_type=request.json.get('movement_type'),
            product_id=request.json.get('product_id'),
            warehouse_id=request.json.get('warehouse_id'),
            quantity=Decimal(request.json.get('quantity')),
            unit_cost=Decimal(request.json.get('unit_cost', 0)),
            reason=request.json.get('reason'),
            notes=request.json.get('notes')
        )
        
        if movement.movement_type == 'transfer':
            movement.destination_warehouse_id = request.json.get('destination_warehouse_id')
        
        # Aplicar movimiento
        movement.apply_movement()
        
        db.session.add(movement)
        db.session.commit()
        
        # Verificar alertas
        stock_item = StockItem.query.filter_by(
            product_id=movement.product_id,
            warehouse_id=movement.warehouse_id
        ).first()
        
        if stock_item and stock_item.needs_reorder:
            alert = StockAlert(
                user_id=current_user.id,
                product_id=movement.product_id,
                warehouse_id=movement.warehouse_id,
                alert_type='low_stock',
                threshold_value=stock_item.reorder_point or stock_item.min_stock,
                current_value=stock_item.quantity,
                message=f'Stock bajo para {stock_item.product.name}'
            )
            db.session.add(alert)
            db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Movimiento registrado exitosamente'
        })
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400

@bp.route('/inventory/movements')
@login_required
@active_business_required
def inventory_movements():
    """Historial de movimientos"""
    page = request.args.get('page', 1, type=int)
    product_id = request.args.get('product', type=int)
    movement_type = request.args.get('type', '')
    
    query = InventoryMovement.query.filter_by(user_id=current_user.id)
    
    if product_id:
        query = query.filter_by(product_id=product_id)
    
    if movement_type:
        query = query.filter_by(movement_type=movement_type)
    
    movements = query.order_by(InventoryMovement.created_at.desc())\
        .paginate(page=page, per_page=50, error_out=False)
    
    return render_template('dashboard/inventory_movements.html',
        movements=movements,
        product_id=product_id,
        movement_type=movement_type
    )

# ==================== CUSTOMER ROUTES ====================

@bp.route('/customers')
@login_required
@active_business_required
def customers():
    """Lista de clientes"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    segment = request.args.get('segment', '')
    
    query = Customer.query.filter_by(user_id=current_user.id)
    
    if search:
        query = query.filter(
            db.or_(
                Customer.name.ilike(f'%{search}%'),
                Customer.email.ilike(f'%{search}%'),
                Customer.phone.ilike(f'%{search}%')
            )
        )
    
    if segment:
        query = query.filter_by(segment=segment)
    
    customers = query.order_by(Customer.created_at.desc())\
        .paginate(page=page, per_page=20, error_out=False)
    
    # Estadísticas
    total_customers = Customer.query.filter_by(user_id=current_user.id).count()
    new_customers = Customer.query.filter(
        Customer.user_id == current_user.id,
        Customer.created_at >= datetime.utcnow() - timedelta(days=30)
    ).count()

    # Calcular estadísticas desde customers_data
    vip_customers_count = sum(1 for customer in customers_data if customer.total_spent >= 5000)
    new_customers_count = sum(1 for customer in customers_data if customer.total_orders == 1)
    at_risk_customers_count = 0  # Placeholder
    marketing_customers_count = 0  # Placeholder

    # Calcular tasa de retorno
    total_customers = len(customers_data)
    returning_customers = sum(1 for customer in customers_data if customer.total_orders > 1)
    returning_rate = (returning_customers / total_customers * 100) if total_customers > 0 else 0
    
    return render_template('dashboard/customers.html',
        customers=customers,
        search=search,
        segment=segment,
        total_customers=total_customers,
        new_customers=new_customers,
        vip_customers_count=vip_customers_count,
        new_customers_count=new_customers_count,
        at_risk_customers_count=at_risk_customers_count,
        marketing_customers_count=marketing_customers_count,
        returning_rate=round(returning_rate, 1)             
    )

@bp.route('/customers/<int:customer_id>')
@login_required
@active_business_required
def customer_detail(customer_id):
    """Detalle de cliente"""
    customer = Customer.query.get_or_404(customer_id)
    
    if customer.user_id != current_user.id:
        flash('No tienes permiso para ver este cliente', 'danger')
        return redirect(url_for('dashboard.customers'))
    
    # Actualizar métricas
    customer.update_metrics()
    db.session.commit()
    
    # Obtener pedidos recientes
    recent_orders = Order.query.filter_by(
        user_id=current_user.id,
        customer_phone=customer.phone
    ).order_by(Order.created_at.desc()).limit(10).all()
    
    # Obtener interacciones
    interactions = customer.interactions.order_by(
        CustomerInteraction.created_at.desc()
    ).limit(10).all()
    
    return render_template('dashboard/customer_detail.html',
        customer=customer,
        recent_orders=recent_orders,
        interactions=interactions
    )

@bp.route('/customers/<int:customer_id>/interaction', methods=['POST'])
@login_required
@active_business_required
def add_customer_interaction(customer_id):
    """Agregar interacción con cliente"""
    customer = Customer.query.get_or_404(customer_id)
    
    if customer.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'No autorizado'}), 403
    
    interaction = CustomerInteraction(
        customer_id=customer.id,
        user_id=current_user.id,
        created_by=current_user.id,
        interaction_type=request.json.get('type'),
        channel=request.json.get('channel'),
        subject=request.json.get('subject'),
        content=request.json.get('content'),
        requires_followup=request.json.get('requires_followup', False)
    )
    
    if interaction.requires_followup:
        followup_date = request.json.get('followup_date')
        if followup_date:
            interaction.followup_date = datetime.strptime(followup_date, '%Y-%m-%d')
    
    db.session.add(interaction)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Interacción registrada exitosamente'
    })

@bp.route('/customers/groups')
@login_required
@active_business_required
def customer_groups():
    """Grupos de clientes"""
    groups = CustomerGroup.query.filter_by(user_id=current_user.id).all()
    
    return render_template('dashboard/customer_groups.html', groups=groups)

@bp.route('/customers/campaigns')
@login_required
@active_business_required
def marketing_campaigns():
    """Campañas de marketing"""
    page = request.args.get('page', 1, type=int)
    
    campaigns = MarketingCampaign.query.filter_by(
        user_id=current_user.id
    ).order_by(
        MarketingCampaign.created_at.desc()
    ).paginate(page=page, per_page=10, error_out=False)
    
    return render_template('dashboard/customer_campaigns.html', campaigns=campaigns)

# ==================== REPORTS ROUTES ====================

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
    """Generar reporte personalizado"""
    report_type = request.json.get('type')
    date_from = datetime.strptime(request.json.get('date_from'), '%Y-%m-%d')
    date_to = datetime.strptime(request.json.get('date_to'), '%Y-%m-%d')
    format_type = request.json.get('format', 'pdf')
    
    # Aquí iría la lógica para generar diferentes tipos de reportes
    # Por ahora retornamos un placeholder
    
    return jsonify({
        'success': True,
        'message': 'Reporte generado',
        'download_url': url_for('dashboard.download_report', report_id='temp')
    })

@bp.route('/reports/download/<report_id>')
@login_required
@active_business_required
def download_report(report_id):
    """Descargar reporte generado"""
    # Implementar lógica de descarga
    flash('Función de descarga en desarrollo', 'info')
    return redirect(url_for('dashboard.reports'))
