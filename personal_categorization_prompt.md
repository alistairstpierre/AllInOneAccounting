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
- **Housing**: Rent, mortgage, utilities, home improvement, maintenance
- **Transportation**: Gas, car payments, public transit, parking, vehicle maintenance
- **Food & Dining**: Groceries, restaurants, cafes, food delivery
- **Healthcare**: Medical expenses, prescriptions, doctor visits, health insurance
- **Personal Care**: Grooming, hygiene products, spa services, fitness memberships
- **Entertainment**: Movies, streaming services, games, hobbies, recreation
- **Shopping**: Clothing, electronics, household items, general retail
- **Insurance**: Health, auto, life, renters insurance
- **Savings/Investing**: Investments, savings accounts, retirement contributions
- **Debt Payment**: Credit card payments, loan payments
- **Education**: Tuition, courses, books, educational materials
- **Travel**: Vacations, flights, hotels, travel expenses
- **Gifts & Donations**: Gifts, charitable donations
- **Uncategorized**: Expenses that don't fit other categories

## Identifying Business Names

When identifying the business name from merchant transaction data:

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

### Food & Dining
- Groceries → Food & Dining
- Restaurants, cafes → Food & Dining
- Food delivery services → Food & Dining

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

### Transportation
- Gas stations → Transportation
- Public transit → Transportation
- Parking → Transportation
- Car maintenance → Transportation

## Important Notes

1. **Both Online and Local**: Personal expenses include both online services (streaming, subscriptions) and local businesses (restaurants, shops). Both are legitimate personal expenses.

2. **Context Matters**: Consider the personal context. For example:
   - "Netflix" → Entertainment (streaming service)
   - "Local Restaurant" → Food & Dining
   - "Gym" → Personal Care (fitness)

3. **When in Doubt**: If an expense could fit multiple categories, choose the most specific one. If truly unclear, use "Uncategorized" and note why.

## Output Format

When categorizing a transaction, provide:
1. **Business Name**: The cleaned business name
2. **Category**: The selected category name
3. **Reasoning**: Brief explanation of why this category was chosen

Example:
```
Business Name: Netflix
Category: Entertainment
Reasoning: Netflix is a streaming service for movies and TV shows, which is a personal entertainment expense.
```

