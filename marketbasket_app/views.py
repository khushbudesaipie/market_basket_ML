from django.shortcuts import render
from django.http import JsonResponse
import pandas as pd
import plotly.express as px
from mlxtend.frequent_patterns import fpgrowth, association_rules
from django.core.paginator import Paginator
from django.core.cache import cache
import json
import random

# Load the dataset
def load_data():
    data = cache.get('retail_data')

    if data is None:
        # file_path = r'Online Retail.xlsx'
        data = pd.read_excel('data\Online Retail.xlsx')
        data = data.drop(columns=['InvoiceNo'])
        data = data[(data.Quantity > 0) & (data.UnitPrice > 0)].dropna(subset=['CustomerID'])
        data.columns = ['itemNo', 'itemName', 'Quantity', 'Date', 'Price', 'CustomerID', 'Country']
        cache.set('retail_data', data, timeout=86400)
    return data


# Home page view
def index(request):
    return render(request, 'index.html', {'title': 'Sales Dashboard'})


# Sales visualizations
def sales_visualizations(request):
    data = load_data()

    # Weekly sales
    sales_weekly = data.resample('W', on='Date').size()
    fig_sales = px.line(x=sales_weekly.index, y=sales_weekly, labels={'y': 'Number of Sales', 'x': 'Date'})
    fig_sales.update_layout(title_text='Number of Sales Weekly', title_x=0.5)

    # Weekly customers
    unique_customers_weekly = data.resample('W', on='Date').CustomerID.nunique()
    fig_customers = px.line(x=unique_customers_weekly.index, y=unique_customers_weekly, labels={'y': 'Number of Customers', 'x': 'Date'})
    fig_customers.update_layout(title_text='Number of Customers Weekly', title_x=0.5)

    # Sales per Customer Ratio
    sales_per_customer = sales_weekly / unique_customers_weekly
    fig_sale_cus = px.line(x=sales_per_customer.index, y=sales_per_customer, labels={'y': 'Sales per Customer Ratio', 'x': 'Date'})
    fig_sale_cus.update_layout(title_text='Sales per Customer Weekly', title_x=0.5)
    fig_sale_cus.update_yaxes(rangemode="tozero")

    # Frequency of Items Sold
    item_sales = data.groupby('itemName').size().reset_index(name='count')
    fig_items = px.treemap(item_sales, path=['itemName'], values='count')
    fig_items.update_layout(title_text='Frequency of Items Sold', title_x=0.5)

    # Top 20 Customers
    top_customers = data.groupby('CustomerID').size().reset_index(name='count').sort_values(by='count', ascending=False).head(20)
    fig_top20 = px.bar(top_customers, x=range(1, 21), y='count', color='count', labels={'x': 'CustomerID', 'y': 'Number of Items Bought'})
    fig_top20.update_layout(title_text='Top 20 Customers by Number of Items Bought', title_x=0.5)

    # Sales per Day of the Week
    day_sales = data.groupby(data['Date'].dt.strftime('%A'))['itemName'].count().reindex(
        ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'])
    fig_day = px.bar(day_sales, x=day_sales.index, y=day_sales, color=day_sales, labels={'y': 'Number of Sales', 'Date': 'Week Days'})
    fig_day.update_layout(title_text='Number of Sales per Day of the Week', title_x=0.5)

    # Sales per Month
    month_sales = data.groupby(data['Date'].dt.strftime('%m'))['itemName'].count()
    fig_month = px.bar(month_sales, x=month_sales.index, y=month_sales, color=month_sales, labels={'y': 'Number of Sales', 'Date': 'Months'})
    fig_month.update_layout(title_text='Number of Sales per Month', title_x=0.5)

    # Sales per Day of the Month
    month_day_sales = data.groupby(data['Date'].dt.strftime('%d'))['itemName'].count()
    fig_monthday = px.bar(month_day_sales, x=month_day_sales.index, y=month_day_sales, color=month_day_sales, labels={'y': 'Number of Sales', 'Date': 'Month Days'})
    fig_monthday.update_layout(title_text='Number of Sales per Day in Month', title_x=0.5)

    context = {
        'fig_sales_html': fig_sales.to_html(full_html=False),
        'fig_customers_html': fig_customers.to_html(full_html=False),
        'fig_sale_cus_html': fig_sale_cus.to_html(full_html=False),
        'fig_items_html': fig_items.to_html(full_html=False),
        'fig_top20_html': fig_top20.to_html(full_html=False),
        'fig_day_html': fig_day.to_html(full_html=False),
        'fig_month_html': fig_month.to_html(full_html=False),
        'fig_monthday_html': fig_monthday.to_html(full_html=False),
    }
    return render(request, 'sales_visualizations.html', context)



def store_view(request):
    # Fetch data from cache
    data = cache.get('retail_data')

    # Convert to list of dictionaries
    data = data.to_dict(orient='records')

    # Apply pagination
    paginator = Paginator(data, 21)  # Show 20 items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Pass the page_obj to the context
    context = {
        'page_obj': page_obj,
    }
    return render(request, 'store.html', context)

def add_to_cart(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        item_name = data.get('item_name')

        # Get the current cart from session, or initialize if not present
        cart = request.session.get('cart', [])

        # Add item to the cart
        if item_name not in cart:
            cart.append(item_name)

        # Save the updated cart back to session
        request.session['cart'] = cart

        return JsonResponse({'cart': cart})

    return JsonResponse({'error': 'Invalid request'}, status=400)

def association_rules_view(request):
    data = load_data()

    # Basket data
    baskets = data.groupby(['CustomerID', 'itemName'])['itemName'].count().unstack().fillna(0).applymap(lambda x: 1 if x >= 1 else 0)

    # Frequent itemsets
    frequent_itemsets = fpgrowth(baskets, min_support=0.025, use_colnames=True, max_len=3)
    rules = association_rules(frequent_itemsets, metric="lift", min_threshold=1)

    # Convert frozensets to strings for display
    rules['antecedents'] = rules['antecedents'].apply(lambda x: ', '.join(list(x)))
    rules['consequents'] = rules['consequents'].apply(lambda x: ', '.join(list(x)))

    rules_list = rules[['antecedents', 'consequents', 'support', 'confidence', 'lift']].to_dict(orient='records')
    cache.set('rules_list', rules_list, timeout=86400)

    query = request.GET.get('q', '')
    if query:
        rules_list = [rule for rule in rules_list if query.lower() in rule['antecedents'].lower() or query.lower() in rule['consequents'].lower()]

    paginator = Paginator(rules_list, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'query': query,
    }

    return render(request, 'association_rules.html', context)



def get_consequents(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        antecedents = ', '.join(data.get('antecedents', '').split(", "))

        rules_list = cache.get('rules_list')
        if rules_list is None:
            return JsonResponse({'error': 'Rules list not found'}, status=404)

        matching_rules = [rule['consequents'] for rule in rules_list if rule['antecedents'] == antecedents]
        return JsonResponse({'consequents': matching_rules or []})

    return JsonResponse({'error': 'Invalid request'}, status=400)
