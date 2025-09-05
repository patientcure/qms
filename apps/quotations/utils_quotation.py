from decimal import Decimal
import logging
from django.http import JsonResponse
from .models import Product, ProductDetails, TermsAndConditions, ActivityLog
from .choices import ActivityAction

logger = logging.getLogger(__name__)


def create_or_update_product_details(quotation, items_data):
    if not quotation._state.adding:
        quotation.details.all().delete()
    product_ids = [item.get('product') for item in items_data if item.get('product')]
    products_cache = {p.id: p for p in Product.objects.filter(id__in=product_ids)}
    product_details_to_create = []
    for item in items_data:
        product_id = item.get('product')
        product_obj = products_cache.get(product_id)
        if not product_obj and item.get('name'):
            product_obj, _ = Product.objects.get_or_create(name=item['name'], defaults={'selling_price': item.get('unit_price', 0)})
        if not product_obj:
            continue
        product_details_to_create.append(ProductDetails(
            quotation=quotation,
            product=product_obj,
            quantity=item.get('quantity', 1),
            unit_price=item.get('unit_price', product_obj.selling_price),
            selling_price=product_obj.selling_price,
            discount=item.get('discount', 0)
        ))
    if product_details_to_create:
        ProductDetails.objects.bulk_create(product_details_to_create)


def log_quotation_changes(quotation, action, user, old_values=None, new_values=None):
    try:
        if action == ActivityAction.QUOTATION_CREATED:
            message = f"Quotation {quotation.quotation_number} created"
        elif action == ActivityAction.QUOTATION_UPDATED:
            changes = []
            if old_values and new_values:
                for field, new_val in new_values.items():
                    old_val = old_values.get(field)
                    if old_val != new_val:
                        changes.append(f"{field}: {old_val} → {new_val}")
            message = f"Quotation {quotation.quotation_number} updated"
            if changes:
                message += f". Changes: {', '.join(changes)}"
        else:
            message = f"Quotation {quotation.quotation_number} - {action}"
        ActivityLog.log(actor=user, action=action, entity=quotation, message=message)
    except Exception as e:
        logger.error(f"Failed to log quotation activity: {str(e)}")


def validate_terms(terms_data):
    if not terms_data:
        return []
    try:
        if isinstance(terms_data, str):
            term_ids = [int(x.strip()) for x in terms_data.split(',') if x.strip()]
        elif isinstance(terms_data, list):
            term_ids = [int(x) for x in terms_data if str(x).strip()]
        else:
            return []
        return list(TermsAndConditions.objects.filter(id__in=term_ids).values_list('id', flat=True))
    except (ValueError, TypeError):
        return []


def recalc_totals_from_items(quotation, items_data):
    if not items_data:
        quotation.subtotal = Decimal('0.00')
        quotation.total = Decimal('0.00')
        quotation.save(update_fields=['subtotal', 'total'])
        return
    gross_subtotal, total_item_discount = Decimal('0.00'), Decimal('0.00')
    for item in items_data:
        quantity = Decimal(str(item.get('quantity', 1)))
        unit_price = Decimal(str(item.get('unit_price', '0.00')))
        discount_percent = Decimal(str(item.get('discount', '0.00')))
        line_gross_total = quantity * unit_price
        item_discount_amount = line_gross_total * (discount_percent / 100)
        gross_subtotal += line_gross_total
        total_item_discount += item_discount_amount
    subtotal_after_item_disc = gross_subtotal - total_item_discount
    tax_amount = Decimal('0.00')
    if quotation.tax_rate and quotation.tax_rate > 0:
        tax_amount = subtotal_after_item_disc * (quotation.tax_rate / Decimal('100.00'))
    total_before_overall_discount = subtotal_after_item_disc + tax_amount
    overall_discount_amount = Decimal('0.00')
    if quotation.discount and quotation.discount > 0:
        if quotation.discount_type == 'amount':
            overall_discount_amount = quotation.discount
        else:
            overall_discount_amount = (subtotal_after_item_disc * quotation.discount / Decimal('100.00'))
    final_total = total_before_overall_discount - overall_discount_amount
    quotation.subtotal = gross_subtotal.quantize(Decimal('0.01'))
    quotation.total = final_total.quantize(Decimal('0.01'))
    quotation.save(update_fields=['subtotal', 'total'])


def handle_validation_errors(form):
    errors = {'form': form.errors}
    return JsonResponse({'success': False, 'errors': errors}, status=400)


def get_quotation_response_data(quotation, lead, term_ids=None):
    try:
        items, gross_subtotal = [], Decimal('0.00')
        for detail in quotation.details.select_related('product').all():
            product = detail.product
            quantity = Decimal(str(detail.quantity))
            unit_price = Decimal(str(detail.unit_price))
            discount_percent = Decimal(str(detail.discount or '0.00'))
            gross_total = quantity * unit_price
            gross_subtotal += gross_total
            discount_amount = gross_total * (discount_percent / 100)
            net_total = gross_total - discount_amount
            items.append({
                'product': {'id': product.id, 'name': product.name},
                'description': product.name,
                'quantity': float(quantity),
                'unit_price': float(unit_price),
                'discount': float(discount_percent),
                'line_total': float(net_total.quantize(Decimal('0.01'))),
            })
        subtotal_after_item_disc = sum(Decimal(str(it['line_total'])) for it in items)
        tax_amount = subtotal_after_item_disc * ((quotation.tax_rate or 0) / 100)
        total_before_overall_discount = subtotal_after_item_disc + tax_amount
        overall_discount_amount = Decimal('0.00')
        if quotation.discount and quotation.discount > 0:
            if quotation.discount_type == 'amount':
                overall_discount_amount = quotation.discount
            else:
                overall_discount_amount = subtotal_after_item_disc * (quotation.discount / 100)
        final_total = total_before_overall_discount - overall_discount_amount
        activity_logs = ActivityLog.objects.filter(entity_type='Quotation', entity_id=str(quotation.id)).select_related('actor').order_by('-created_at')[:10]
        logs_data = [{'id': log.id, 'action': log.action, 'message': log.message, 'actor': {'id': log.actor.id if log.actor else None, 'name': log.actor.get_full_name() if log.actor else 'System'}, 'created_at': log.created_at} for log in activity_logs]
        return {
            'id': quotation.id,
            'quotation_number': quotation.quotation_number,
            'status': quotation.status,
            'subtotal': float(gross_subtotal.quantize(Decimal('0.01'))),
            'tax_rate': float(quotation.tax_rate or 0),
            'total': float(final_total.quantize(Decimal('0.01'))),
            'discount': float(quotation.discount) if quotation.discount else 0.0,
            'discount_type': quotation.discount_type,
            'currency': quotation.currency,
            'customer': {'id': quotation.customer.id, 'name': quotation.customer.name, 'email': quotation.customer.email, 'phone': quotation.customer.phone},
            'assigned_to': {'id': quotation.assigned_to.id, 'name': quotation.assigned_to.get_full_name()} if quotation.assigned_to else None,
            'lead': {'id': lead.id, 'status': lead.status, 'priority': lead.priority, 'follow_up_date': lead.follow_up_date, 'quotation_id': lead.quotation_id, 'notes': lead.notes} if lead else None,
            'follow_up_date': quotation.follow_up_date,
            'created_at': quotation.created_at,
            'items': items,
            'terms': term_ids if term_ids else [],
            'activity_logs': logs_data
        }
    except Exception as e:
        logger.error(f"Error preparing quotation response data: {str(e)}")
        return {'id': quotation.id, 'quotation_number': quotation.quotation_number, 'error': 'Failed to serialize response'}
