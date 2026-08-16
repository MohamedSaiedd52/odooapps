# -*- coding: utf-8 -*-
import logging
import json
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)

class ShopifyAnalytics(models.Model):
    _name = 'shopify.analytics'
    _description = 'Shopify Analytics Dashboard'
    _order = 'id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Analytics Name', required=True, tracking=True, default=lambda self: f"Analytics Report {fields.Date.today()}")
    instance_id = fields.Many2one('shopify.instance', string='Shopify Instance', required=True, ondelete='cascade', default=lambda self: self._default_instance_id())
    
    # Time Period
    date_from = fields.Date('From Date', required=True, tracking=True)
    date_to = fields.Date('To Date', required=True, tracking=True)
    period_type = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ], string='Period Type', default='monthly', tracking=True)
    
    # Sales Analytics
    total_sales = fields.Monetary('Total Sales', currency_field='currency_id', compute='_compute_sales_analytics')
    total_orders = fields.Integer('Total Orders', compute='_compute_sales_analytics')
    average_order_value = fields.Monetary('Average Order Value', currency_field='currency_id', compute='_compute_sales_analytics')
    conversion_rate = fields.Float('Conversion Rate (%)', compute='_compute_sales_analytics')
    revenue_growth = fields.Float('Revenue Growth (%)', compute='_compute_sales_analytics')
    
    # Customer Analytics
    total_customers = fields.Integer('Total Customers', compute='_compute_customer_analytics')
    new_customers = fields.Integer('New Customers', compute='_compute_customer_analytics')
    returning_customers = fields.Integer('Returning Customers', compute='_compute_customer_analytics')
    customer_acquisition_cost = fields.Monetary('Customer Acquisition Cost', currency_field='currency_id', compute='_compute_customer_analytics')
    customer_lifetime_value = fields.Monetary('Customer Lifetime Value', currency_field='currency_id', compute='_compute_customer_analytics')
    
    # Product Analytics
    total_products = fields.Integer('Total Products', compute='_compute_product_analytics')
    top_selling_products = fields.Text('Top Selling Products', compute='_compute_product_analytics')
    low_stock_products = fields.Text('Low Stock Products', compute='_compute_product_analytics')
    product_performance_score = fields.Float('Product Performance Score', compute='_compute_product_analytics')
    
    # Inventory Analytics
    total_inventory_value = fields.Monetary('Total Inventory Value', currency_field='currency_id', compute='_compute_inventory_analytics')
    inventory_turnover_rate = fields.Float('Inventory Turnover Rate', compute='_compute_inventory_analytics')
    stockout_incidents = fields.Integer('Stockout Incidents', compute='_compute_inventory_analytics')
    reorder_recommendations = fields.Text('Reorder Recommendations', compute='_compute_inventory_analytics')
    
    # Financial Analytics
    gross_profit_margin = fields.Float('Gross Profit Margin (%)', compute='_compute_financial_analytics')
    net_profit_margin = fields.Float('Net Profit Margin (%)', compute='_compute_financial_analytics')
    operating_expenses = fields.Monetary('Operating Expenses', currency_field='currency_id', compute='_compute_financial_analytics')
    cash_flow = fields.Monetary('Cash Flow', currency_field='currency_id', compute='_compute_financial_analytics')
    
    # Performance Metrics
    order_fulfillment_rate = fields.Float('Order Fulfillment Rate (%)', compute='_compute_performance_analytics')
    average_processing_time = fields.Float('Average Processing Time (Hours)', compute='_compute_performance_analytics')
    customer_satisfaction_score = fields.Float('Customer Satisfaction Score', compute='_compute_performance_analytics')
    return_rate = fields.Float('Return Rate (%)', compute='_compute_performance_analytics')
    
    # AI Insights
    ai_insights = fields.Text('AI Insights', compute='_compute_ai_insights')
    risk_alerts = fields.Text('Risk Alerts', compute='_compute_ai_insights')
    optimization_recommendations = fields.Text('Optimization Recommendations', compute='_compute_ai_insights')
    
    # Chart Data
    sales_chart_data = fields.Json('Sales Chart Data', compute='_compute_chart_data')
    customer_chart_data = fields.Json('Customer Chart Data', compute='_compute_chart_data')
    product_chart_data = fields.Json('Product Chart Data', compute='_compute_chart_data')
    inventory_chart_data = fields.Json('Inventory Chart Data', compute='_compute_chart_data')
    
    # Configuration
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 default=lambda self: self.env.company.currency_id)
    base_currency_id = fields.Many2one('res.currency', string='Base Currency', 
                                      default=lambda self: self.env.company.currency_id)
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('error', 'Error'),
    ], string='Status', default='draft', tracking=True)
    
    # Audit
    last_updated = fields.Datetime('Last Updated', default=fields.Datetime.now, readonly=True)
    generated_by = fields.Many2one('res.users', string='Generated By', default=lambda self: self.env.user)
    
    note = fields.Text('Notes')

    @api.model
    def _default_instance_id(self):
        """Return the first connected instance as default"""
        return self.env['shopify.instance'].search([
            ('state', '=', 'connected'),
            ('active', '=', True)
        ], limit=1)

    @api.depends('date_from', 'date_to', 'instance_id')
    def _compute_sales_analytics(self):
        for record in self:
            orders = self._get_orders_in_period(record)

            # Use total_price from shopify.order (not amount_total from sale.order)
            record.total_sales = sum(orders.mapped('total_price'))
            record.total_orders = len(orders)
            record.average_order_value = record.total_sales / record.total_orders if record.total_orders > 0 else 0

            # Calculate conversion rate (orders / visitors)
            visitors = self._get_visitors_in_period(record)
            record.conversion_rate = (record.total_orders / visitors * 100) if visitors > 0 else 0

            # Calculate revenue growth
            previous_period_sales = self._get_previous_period_sales(record)
            record.revenue_growth = ((record.total_sales - previous_period_sales) / previous_period_sales * 100) if previous_period_sales > 0 else 0

    @api.depends('date_from', 'date_to', 'instance_id')
    def _compute_customer_analytics(self):
        for record in self:
            customers = self._get_customers_in_period(record)

            record.total_customers = len(customers)
            # Compare date part only (create_date is datetime, date_from is date)
            if record.date_from:
                date_from_dt = datetime.combine(record.date_from, datetime.min.time())
                record.new_customers = len(customers.filtered(lambda c: c.create_date and c.create_date >= date_from_dt))
            else:
                record.new_customers = 0
            record.returning_customers = record.total_customers - record.new_customers

            # Calculate customer acquisition cost
            marketing_costs = self._get_marketing_costs_in_period(record)
            record.customer_acquisition_cost = marketing_costs / record.new_customers if record.new_customers > 0 else 0

            # Calculate customer lifetime value
            record.customer_lifetime_value = record.total_sales / record.total_customers if record.total_customers > 0 else 0

    @api.depends('date_from', 'date_to', 'instance_id')
    def _compute_product_analytics(self):
        for record in self:
            products = self._get_products_in_period(record)
            
            record.total_products = len(products)
            
            # Get top selling products
            top_products = self._get_top_selling_products(record)
            record.top_selling_products = json.dumps(top_products)
            
            # Get low stock products
            low_stock_products = self._get_low_stock_products(record)
            record.low_stock_products = json.dumps(low_stock_products)
            
            # Calculate product performance score
            record.product_performance_score = self._calculate_product_performance_score(record)

    @api.depends('date_from', 'date_to', 'instance_id')
    def _compute_inventory_analytics(self):
        for record in self:
            # Calculate total inventory value
            products = self._get_products_in_period(record)
            record.total_inventory_value = sum(products.mapped(lambda p: p.qty_available * p.standard_price))
            
            # Calculate inventory turnover rate
            record.inventory_turnover_rate = self._calculate_inventory_turnover_rate(record)
            
            # Count stockout incidents
            record.stockout_incidents = self._count_stockout_incidents(record)
            
            # Generate reorder recommendations
            reorder_recs = self._generate_reorder_recommendations(record)
            record.reorder_recommendations = json.dumps(reorder_recs)

    @api.depends('date_from', 'date_to', 'instance_id')
    def _compute_financial_analytics(self):
        for record in self:
            # Calculate gross profit margin
            total_cost = self._get_total_cost_in_period(record)
            record.gross_profit_margin = ((record.total_sales - total_cost) / record.total_sales * 100) if record.total_sales > 0 else 0
            
            # Calculate net profit margin
            operating_expenses = self._get_operating_expenses_in_period(record)
            record.operating_expenses = operating_expenses
            record.net_profit_margin = ((record.total_sales - total_cost - operating_expenses) / record.total_sales * 100) if record.total_sales > 0 else 0
            
            # Calculate cash flow
            record.cash_flow = record.total_sales - total_cost - operating_expenses

    @api.depends('date_from', 'date_to', 'instance_id')
    def _compute_performance_analytics(self):
        for record in self:
            # Calculate order fulfillment rate
            fulfilled_orders = self._get_fulfilled_orders_in_period(record)
            record.order_fulfillment_rate = (len(fulfilled_orders) / record.total_orders * 100) if record.total_orders > 0 else 0
            
            # Calculate average processing time
            record.average_processing_time = self._calculate_average_processing_time(record)
            
            # Calculate customer satisfaction score
            record.customer_satisfaction_score = self._calculate_customer_satisfaction_score(record)
            
            # Calculate return rate
            returned_orders = self._get_returned_orders_in_period(record)
            record.return_rate = (len(returned_orders) / record.total_orders * 100) if record.total_orders > 0 else 0

    @api.depends('date_from', 'date_to', 'instance_id')
    def _compute_ai_insights(self):
        for record in self:
            # Generate AI insights
            insights = self._generate_ai_insights(record)
            record.ai_insights = json.dumps(insights)
            
            # Generate risk alerts
            risks = self._generate_risk_alerts(record)
            record.risk_alerts = json.dumps(risks)
            
            # Generate optimization recommendations
            recommendations = self._generate_optimization_recommendations(record)
            record.optimization_recommendations = json.dumps(recommendations)

    @api.depends('date_from', 'date_to', 'instance_id', 'period_type')
    def _compute_chart_data(self):
        for record in self:
            # Generate sales chart data
            record.sales_chart_data = self._generate_sales_chart_data(record)

            # Generate customer chart data
            record.customer_chart_data = self._generate_customer_chart_data(record)

            # Generate product chart data
            record.product_chart_data = self._generate_product_chart_data(record)

            # Generate inventory chart data
            record.inventory_chart_data = self._generate_inventory_chart_data(record)

    def _get_orders_in_period(self, record):
        """Get orders within the specified period - directly from Shopify orders"""
        if not record.instance_id or not record.date_from or not record.date_to:
            return self.env['shopify.order'].browse()

        # Search directly in shopify.order using order_date field
        shopify_orders = self.env['shopify.order'].search([
            ('instance_id', '=', record.instance_id.id),
            ('order_date', '>=', record.date_from),
            ('order_date', '<=', record.date_to),
        ])
        return shopify_orders

    def _get_customers_in_period(self, record):
        """Get customers within the specified period - from Shopify customers"""
        if not record.instance_id or not record.date_from or not record.date_to:
            return self.env['shopify.customer'].browse()

        # Get Shopify customers directly
        shopify_customers = self.env['shopify.customer'].search([
            ('instance_id', '=', record.instance_id.id),
            ('create_date', '>=', record.date_from),
            ('create_date', '<=', record.date_to)
        ])
        return shopify_customers

    def _get_products_in_period(self, record):
        """Get products within the specified period"""
        shopify_products = self.env['shopify.product'].search([
            ('instance_id', '=', record.instance_id.id)
        ])
        return shopify_products.mapped('odoo_product_id')

    def _get_visitors_in_period(self, record):
        """Get visitors within the specified period (placeholder)"""
        # This would integrate with analytics platforms like Google Analytics
        return 1000  # Placeholder

    def _get_previous_period_sales(self, record):
        """Get sales from previous period for growth calculation"""
        if not record.date_from or not record.date_to:
            return 0
        try:
            period_days = (record.date_to - record.date_from).days
            if period_days <= 0:
                return 0
            previous_date_from = record.date_from - timedelta(days=period_days)
            previous_date_to = record.date_from - timedelta(days=1)

            previous_shopify_orders = self.env['shopify.order'].search([
                ('instance_id', '=', record.instance_id.id),
                ('odoo_order_id.date_order', '>=', previous_date_from),
                ('odoo_order_id.date_order', '<=', previous_date_to),
                ('odoo_order_id.state', 'in', ['sale', 'done'])
            ])

            return sum(previous_shopify_orders.mapped('odoo_order_id.amount_total') or [0])
        except Exception:
            return 0

    def _get_marketing_costs_in_period(self, record):
        """Get marketing costs within the specified period"""
        # This would integrate with marketing platforms
        return 5000  # Placeholder

    def _get_top_selling_products(self, record):
        """Get top selling products from Shopify order line items"""
        if not record.instance_id or not record.date_from or not record.date_to:
            return []

        # Primary: Get data from shopify.order.line (direct from Shopify)
        order_lines = self.env['shopify.order.line'].search([
            ('order_id.instance_id', '=', record.instance_id.id),
            ('order_id.order_date', '>=', record.date_from),
            ('order_id.order_date', '<=', record.date_to),
        ])

        if order_lines:
            # Group by product (use title as key since shopify_product_id may not exist)
            product_sales = {}
            for line in order_lines:
                # Use shopify_product_id if available, otherwise use title
                key = line.shopify_product_id or line.title or 'Unknown'
                product_name = line.title or 'Unknown Product'

                if key not in product_sales:
                    product_sales[key] = {
                        'name': product_name,
                        'qty': 0,
                        'revenue': 0
                    }
                product_sales[key]['qty'] += line.quantity
                product_sales[key]['revenue'] += line.net_price

            # Sort by revenue and return top 10
            sorted_products = sorted(product_sales.values(), key=lambda x: x['revenue'], reverse=True)
            return [
                {'name': p['name'], 'quantity': p['qty'], 'revenue': p['revenue']}
                for p in sorted_products[:10]
            ]

        # Fallback: Try to get from linked Odoo orders (sale.order.order_line)
        orders = self._get_orders_in_period(record)
        product_sales = {}

        for order in orders:
            if order.odoo_order_id and order.odoo_order_id.order_line:
                for line in order.odoo_order_id.order_line:
                    if line.product_id:
                        product_id = line.product_id.id
                        if product_id not in product_sales:
                            product_sales[product_id] = {'qty': 0, 'revenue': 0}
                        product_sales[product_id]['qty'] += line.product_uom_qty
                        product_sales[product_id]['revenue'] += line.price_subtotal

        if product_sales:
            sorted_products = sorted(product_sales.items(), key=lambda x: x[1]['revenue'], reverse=True)
            top_products = []
            for product_id, data in sorted_products[:10]:
                product = self.env['product.product'].browse(product_id)
                top_products.append({
                    'name': product.name,
                    'quantity': data['qty'],
                    'revenue': data['revenue']
                })
            return top_products

        # No real product sales data available
        return []

    def _get_low_stock_products(self, record):
        """Get products with low stock"""
        products = self._get_products_in_period(record)
        low_stock_products = []
        
        for product in products:
            # Use a default reorder point of 10 if not set
            reorder_point = getattr(product, 'reorder_min_qty', 10)
            if product.qty_available <= reorder_point:
                low_stock_products.append({
                    'name': product.name,
                    'current_stock': product.qty_available,
                    'reorder_point': reorder_point,
                    'recommended_order': reorder_point - product.qty_available
                })
        
        return low_stock_products

    def _calculate_product_performance_score(self, record):
        """Calculate product performance score"""
        products = self._get_products_in_period(record)
        if not products:
            return 0
        
        total_score = 0
        for product in products:
            # Calculate score based on available metrics
            # Use safe defaults for fields that might not exist
            sales_count = getattr(product, 'sales_count', 0)
            gross_profit_margin = getattr(product, 'gross_profit_margin', 0)
            inventory_turnover_rate = getattr(product, 'inventory_turnover_rate', 0)
            
            sales_score = min(sales_count / 100, 1) * 40  # Max 40 points
            profit_score = min(gross_profit_margin / 50, 1) * 30  # Max 30 points
            turnover_score = min(inventory_turnover_rate / 10, 1) * 30  # Max 30 points
            
            total_score += sales_score + profit_score + turnover_score
        
        return total_score / len(products)

    def _calculate_inventory_turnover_rate(self, record):
        """Calculate inventory turnover rate"""
        # This is a simplified calculation
        products = self._get_products_in_period(record)
        if not products:
            return 0
        
        total_cost_of_goods_sold = sum(products.mapped(lambda p: getattr(p, 'sales_count', 0) * p.standard_price))
        average_inventory = sum(products.mapped('qty_available')) / len(products)
        
        return total_cost_of_goods_sold / average_inventory if average_inventory > 0 else 0

    def _count_stockout_incidents(self, record):
        """Count stockout incidents"""
        # This would integrate with inventory management system
        return 5  # Placeholder

    def _generate_reorder_recommendations(self, record):
        """Generate reorder recommendations"""
        products = self._get_products_in_period(record)
        recommendations = []
        
        for product in products:
            reorder_min_qty = getattr(product, 'reorder_min_qty', 10)
            reorder_max_qty = getattr(product, 'reorder_max_qty', 50)
            
            if product.qty_available <= reorder_min_qty:
                recommended_qty = reorder_max_qty - product.qty_available
                recommendations.append({
                    'product_name': product.name,
                    'current_stock': product.qty_available,
                    'recommended_order': recommended_qty,
                    'urgency': 'high' if product.qty_available == 0 else 'medium'
                })
        
        return recommendations

    def _get_total_cost_in_period(self, record):
        """Get total cost of goods sold in period from Shopify orders"""
        orders = self._get_orders_in_period(record)
        total_cost = 0

        # Try to get cost data from linked Odoo orders (sale.order)
        for order in orders:
            if order.odoo_order_id and order.odoo_order_id.order_line:
                for line in order.odoo_order_id.order_line:
                    if line.product_id:
                        total_cost += line.product_uom_qty * line.product_id.standard_price

        # If no linked orders with cost data, estimate based on total sales
        # Assuming average 60% cost ratio (placeholder estimation)
        if total_cost == 0 and orders:
            total_sales = sum(orders.mapped('total_price'))
            total_cost = total_sales * 0.6  # Placeholder: 60% cost ratio

        return total_cost

    def _get_operating_expenses_in_period(self, record):
        """Get operating expenses in period"""
        # This would integrate with accounting system
        return 10000  # Placeholder

    def _get_fulfilled_orders_in_period(self, record):
        """Get fulfilled orders in period"""
        shopify_orders = self.env['shopify.order'].search([
            ('instance_id', '=', record.instance_id.id),
            ('odoo_order_id.date_order', '>=', record.date_from),
            ('odoo_order_id.date_order', '<=', record.date_to),
            ('odoo_order_id.state', '=', 'done')
        ])
        return shopify_orders.mapped('odoo_order_id')

    def _calculate_average_processing_time(self, record):
        """Calculate average order processing time"""
        # Shopify orders don't have processing time tracking
        # Return placeholder value
        return 24.0  # Placeholder: 24 hours average

    def _calculate_customer_satisfaction_score(self, record):
        """Calculate customer satisfaction score"""
        # This would integrate with customer feedback systems
        return 4.2  # Placeholder

    def _get_returned_orders_in_period(self, record):
        """Get returned orders in period"""
        # This would integrate with returns management system
        shopify_orders = self.env['shopify.order'].search([
            ('instance_id', '=', record.instance_id.id),
            ('odoo_order_id.date_order', '>=', record.date_from),
            ('odoo_order_id.date_order', '<=', record.date_to),
            ('odoo_order_id.state', '=', 'cancel')
        ])
        return shopify_orders.mapped('odoo_order_id')

    def _generate_ai_insights(self, record):
        """Generate AI-powered insights"""
        insights = []
        
        # Sales insights
        if record.revenue_growth > 20:
            insights.append("Strong revenue growth detected - consider expanding inventory")
        elif record.revenue_growth < -10:
            insights.append("Revenue decline detected - review pricing and marketing strategy")
        
        # Customer insights
        if record.customer_acquisition_cost > record.customer_lifetime_value:
            insights.append("Customer acquisition cost exceeds lifetime value - optimize marketing spend")
        
        # Inventory insights
        if record.inventory_turnover_rate < 2:
            insights.append("Low inventory turnover - consider promotions or price adjustments")
        
        return insights

    def _generate_risk_alerts(self, record):
        """Generate risk alerts"""
        risks = []
        
        # Stockout risks
        if record.stockout_incidents > 10:
            risks.append("High stockout incidents - review inventory management")
        
        # Customer satisfaction risks
        if record.customer_satisfaction_score < 3.5:
            risks.append("Low customer satisfaction - investigate service issues")
        
        # Financial risks
        if record.net_profit_margin < 5:
            risks.append("Low profit margin - review pricing and costs")
        
        return risks

    def _generate_optimization_recommendations(self, record):
        """Generate optimization recommendations"""
        recommendations = []
        
        # Sales optimization
        if record.conversion_rate < 2:
            recommendations.append("Low conversion rate - optimize website and checkout process")
        
        # Inventory optimization
        if record.inventory_turnover_rate < 3:
            recommendations.append("Improve inventory turnover with better demand forecasting")
        
        # Customer optimization
        if record.customer_lifetime_value < record.customer_acquisition_cost * 3:
            recommendations.append("Focus on customer retention and upselling strategies")
        
        return recommendations

    def _get_period_key(self, date_obj, period_type):
        """Get the grouping key based on period type"""
        if period_type == 'daily':
            return date_obj.strftime('%Y-%m-%d')
        elif period_type == 'weekly':
            # Get the Monday of the week
            week_start = date_obj - timedelta(days=date_obj.weekday())
            return f"Week {week_start.strftime('%Y-%m-%d')}"
        elif period_type == 'monthly':
            return date_obj.strftime('%Y-%m')
        elif period_type == 'quarterly':
            quarter = (date_obj.month - 1) // 3 + 1
            return f"{date_obj.year}-Q{quarter}"
        elif period_type == 'yearly':
            return str(date_obj.year)
        else:
            return date_obj.strftime('%Y-%m-%d')

    def _generate_sales_chart_data(self, record):
        """Generate sales chart data from Shopify orders grouped by period_type"""
        orders = self._get_orders_in_period(record)
        period_type = record.period_type or 'daily'

        # Group by period_type
        sales_by_period = {}
        for order in orders:
            if order.order_date:
                period_key = self._get_period_key(order.order_date, period_type)
                if period_key not in sales_by_period:
                    sales_by_period[period_key] = 0
                sales_by_period[period_key] += order.total_price

        # Sort by key
        sorted_data = sorted(sales_by_period.items(), key=lambda x: x[0])

        return {
            'labels': [item[0] for item in sorted_data],
            'values': [item[1] for item in sorted_data],
            'type': 'line'
        }

    def _generate_customer_chart_data(self, record):
        """Generate customer chart data grouped by period_type"""
        customers = self._get_customers_in_period(record)
        period_type = record.period_type or 'daily'

        # Group by period_type
        customers_by_period = {}
        for customer in customers:
            if customer.create_date:
                period_key = self._get_period_key(customer.create_date.date(), period_type)
                if period_key not in customers_by_period:
                    customers_by_period[period_key] = 0
                customers_by_period[period_key] += 1

        # Sort by key
        sorted_data = sorted(customers_by_period.items(), key=lambda x: x[0])

        return {
            'labels': [item[0] for item in sorted_data],
            'values': [item[1] for item in sorted_data],
            'type': 'bar'
        }

    def _generate_product_chart_data(self, record):
        """Generate product chart data using revenue"""
        top_products = json.loads(record.top_selling_products or '[]')

        # Use revenue for pie chart (more meaningful than quantity)
        labels = [p['name'] for p in top_products if p.get('revenue', 0) > 0]
        values = [p['revenue'] for p in top_products if p.get('revenue', 0) > 0]

        # If no revenue data, fall back to showing products equally
        if not values and top_products:
            labels = [p['name'] for p in top_products]
            values = [1] * len(labels)

        return {
            'labels': labels,
            'values': values,
            'type': 'pie'
        }

    def _generate_inventory_chart_data(self, record):
        """Generate inventory chart data"""
        products = self._get_products_in_period(record)
        
        # Group by stock level
        stock_levels = {
            'In Stock': len(products.filtered(lambda p: p.qty_available > getattr(p, 'reorder_min_qty', 10))),
            'Low Stock': len(products.filtered(lambda p: 0 < p.qty_available <= getattr(p, 'reorder_min_qty', 10))),
            'Out of Stock': len(products.filtered(lambda p: p.qty_available == 0))
        }
        
        return {
            'labels': list(stock_levels.keys()),
            'values': list(stock_levels.values()),
            'type': 'doughnut'
        }

    def action_generate_analytics(self):
        """Generate analytics for the specified period"""
        for record in self:
            record.state = 'processing'
            try:
                # Trigger all computed fields
                record._compute_sales_analytics()
                record._compute_customer_analytics()
                record._compute_product_analytics()
                record._compute_inventory_analytics()
                record._compute_financial_analytics()
                record._compute_performance_analytics()
                record._compute_ai_insights()
                record._compute_chart_data()
                
                record.state = 'completed'
                record.last_updated = fields.Datetime.now()
                record.message_post(body=_('Analytics generated successfully'))
            except Exception as e:
                record.state = 'error'
                record.message_post(body=_('Failed to generate analytics: %s') % str(e))
                raise UserError(_('Failed to generate analytics: %s') % str(e))

    def action_export_report(self):
        """Export analytics report"""
        for record in self:
            # Generate report data
            report_data = {
                'analytics_name': record.name,
                'period': f"{record.date_from} to {record.date_to}",
                'sales_summary': {
                    'total_sales': record.total_sales,
                    'total_orders': record.total_orders,
                    'average_order_value': record.average_order_value,
                    'revenue_growth': record.revenue_growth,
                },
                'customer_summary': {
                    'total_customers': record.total_customers,
                    'new_customers': record.new_customers,
                    'customer_lifetime_value': record.customer_lifetime_value,
                },
                'ai_insights': json.loads(record.ai_insights or '[]'),
                'risk_alerts': json.loads(record.risk_alerts or '[]'),
                'recommendations': json.loads(record.optimization_recommendations or '[]'),
            }
            
            # Return report data (could be used for PDF generation, Excel export, etc.)
            return report_data

    @api.model
    def create(self, vals):
        """Override create to set default values"""
        if not vals.get('date_from'):
            vals['date_from'] = (datetime.now() - timedelta(days=30)).date()
        if not vals.get('date_to'):
            vals['date_to'] = datetime.now().date()
        
        return super().create(vals)

    def write(self, vals):
        """Override write to trigger analytics generation"""
        result = super().write(vals)
        
        # If period changed, regenerate analytics
        if 'date_from' in vals or 'date_to' in vals:
            for record in self:
                if record.state == 'completed':
                    record.action_generate_analytics()
        
        return result

    @api.model
    def _cron_generate_analytics(self):
        """Cron job to generate analytics for all active instances"""
        instances = self.env['shopify.instance'].search([
            ('state', '=', 'connected'),
            ('active', '=', True)
        ])
        for instance in instances:
            try:
                # Create or update analytics record for current month
                date_from = datetime.now().replace(day=1).date()
                date_to = datetime.now().date()

                analytics = self.search([
                    ('instance_id', '=', instance.id),
                    ('date_from', '=', date_from),
                ], limit=1)

                if not analytics:
                    analytics = self.create({
                        'name': f"Monthly Analytics - {instance.name} - {date_from.strftime('%Y-%m')}",
                        'instance_id': instance.id,
                        'date_from': date_from,
                        'date_to': date_to,
                    })

                analytics.action_generate_analytics()
            except Exception as e:
                _logger.error("Cron analytics generation error for %s: %s", instance.name, str(e))

    @api.model
    def _cron_daily_summary(self):
        """Cron job to generate daily summary report"""
        instances = self.env['shopify.instance'].search([
            ('state', '=', 'connected'),
            ('active', '=', True)
        ])
        for instance in instances:
            try:
                # Create daily analytics
                today = datetime.now().date()
                analytics = self.create({
                    'name': f"Daily Summary - {instance.name} - {today}",
                    'instance_id': instance.id,
                    'date_from': today,
                    'date_to': today,
                    'period_type': 'daily',
                })
                analytics.action_generate_analytics()
            except Exception as e:
                _logger.error("Cron daily summary error for %s: %s", instance.name, str(e)) 