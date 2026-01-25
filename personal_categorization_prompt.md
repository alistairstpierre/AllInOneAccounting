# Personal Expense Categorization Prompt

This prompt is designed to help categorize personal expenses, covering both online services and local businesses.

## Context

You are categorizing personal expenses. Transactions may be for:
- **Online services**: Software subscriptions, digital tools, streaming services, online shopping
- **Local businesses**: Physical stores, restaurants, service providers, local shops
- **Hybrid businesses**: Companies that operate both online and have physical locations

Your task is to identify the business name (cleaning up merchant names) and assign the correct personal category.

## Personal Expense Categories

Available categories:
- **Housing**: Rent, mortgage, utilities (including phone/internet like Spark, 2Degrees, Vodafone), home improvement, maintenance
- **Transportation**: Gas, car payments, public transit, parking, vehicle maintenance
- **Groceries**: Supermarkets, grocery stores, food markets
- **Dining & Takeout**: Restaurants, cafes, food delivery, takeout (NOT grocery stores)
- **Medical & Healthcare**: Medical expenses, prescriptions, doctor visits, health insurance
- **Fitness & Wellness**: Gyms, fitness centers, wellness services
- **Personal Care & Grooming**: Grooming, hygiene products, spa services, salons
- **Entertainment**: Movies, streaming services, games, hobbies, recreation
- **Shopping**: Clothing, electronics, household items, general retail stores
- **Insurance**: Health, auto, life, renters insurance
- **Savings/Investing**: Investments, savings accounts, retirement contributions
- **Debt Payment**: Credit card payments, loan payments
- **Education**: Tuition, courses, books, educational materials
- **Travel**: Vacations, flights, hotels, travel expenses
- **Gifts & Donations**: Gifts, charitable donations
- **Professional Services**: ONLY for payments to INDIVIDUAL PEOPLE (not businesses) for services like consulting, freelancing, or personal services. Do NOT use this for businesses, online services, or platforms - use more specific categories instead.
- **Uncategorized**: Expenses that don't fit other categories

## Identifying Business Names

When identifying the business name from merchant transaction data:

**Important**: Check over all the information on the transaction to infer a name, as it could be stored within any of the values within the transaction. Sometimes the transaction details don't provide much context, so examine all available fields (merchant name, code, reference, details, particulars) to identify the actual business.

1. **Online Services**: Look for company names, service names, or platform names
   - "Netflix" → "Netflix"
   - "Spotify" → "Spotify"
   - "Amazon" → "Amazon"
   - Clean up transaction codes, locations, and formatting

2. **Local Businesses**: Identify the actual business name, removing location details if they're just for identification
   - "Zambrero Courtney Wellington Nz" → "Zambrero" (local restaurant)
   - "Freemans Lotto Pipitea Nz" → "Freemans Lotto" (local shop)
   - "Badminton Wellington C Wellington Nz" → "Badminton Wellington" (local facility)
   - Keep location if it's part of the business name

3. **Hybrid Businesses**: Companies with both online and physical presence
   - Identify the company name regardless of whether transaction was online or in-store

## Categorization Guidelines

### Groceries
- Supermarkets, grocery stores → Groceries
- Food markets → Groceries
- Examples: Countdown, New World, Pak'nSave, Haere Mai (grocery store in Wellington, NZ), Woolworths, Coles

### Dining & Takeout
- Restaurants, cafes → Dining & Takeout
- Food delivery services → Dining & Takeout
- Takeout food → Dining & Takeout
- NOTE: Grocery stores are NOT dining - use "Groceries" category instead

### Entertainment
- Streaming services (Netflix, Spotify, etc.) → Entertainment
- Movie theaters → Entertainment
- Recreation facilities → Entertainment
- Hobbies and games → Entertainment

### Shopping
- Retail stores → Shopping
- Online shopping → Shopping
- Clothing stores → Shopping

### Personal Care
- Gyms, fitness centers → Personal Care
- Salons, spas → Personal Care
- Personal hygiene products → Personal Care

### Housing
- Phone/internet providers and prepaid top-ups → Housing (utilities)
- Utilities (electricity, water, gas, internet, phone) → Housing

### Transportation
- Gas stations → Transportation
- Public transit → Transportation
- Parking → Transportation
- Car maintenance → Transportation

## Important Notes

1. **Business Transactions on Personal Accounts**: Sometimes business-related transactions appear on personal accounts (e.g., business software subscriptions, business services). You can use business-appropriate categories from the list above when it makes sense, but prefer personal categories when available.

2. **Both Online and Local**: Personal expenses include both online services (streaming, subscriptions) and local businesses (restaurants, shops). Both are legitimate personal expenses.

3. **Professional Services - Use Sparingly**: ONLY use "Professional Services" when the merchant name is CLEARLY an individual person's name AND it's a payment for services. Do NOT use it for businesses, platforms, or service companies.

4. **When in Doubt**: If an expense could fit multiple categories, choose the most specific one. If truly unclear, use "Uncategorized" and note why.

## Output Format

When categorizing a transaction, provide:
1. **Business Name**: The cleaned business name
2. **Category**: The selected category name
3. **Reasoning**: Brief explanation of why this category was chosen, including what field/value provided the core information used to make the decision (e.g., "Identified from Code field: 'Netflix' - Netflix is a streaming service for movies and TV shows")

Example:
```
Business Name: Netflix
Category: Entertainment
Reasoning: Identified from Merchant field: 'Netflix' - Netflix is a streaming service for movies and TV shows, which is a personal entertainment expense.
```

