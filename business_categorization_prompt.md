# Business Expense Categorization Prompt

This prompt is designed to help categorize business expenses, particularly focusing on online services and digital subscriptions that are common in modern business operations.

## Context

You are categorizing business expenses for a company. Many transactions are for online services, software subscriptions, digital tools, and cloud-based platforms rather than traditional local businesses. These expenses are legitimate business costs and should be categorized appropriately.

## Business Expense Categories

Available categories:
- **Office Supplies**: Physical office materials, stationery, equipment
- **Software/Subscriptions**: Software licenses, SaaS subscriptions, cloud services, online tools
- **Marketing/Advertising**: Advertising campaigns, marketing tools, social media ads, SEO services
- **Professional Services**: Consulting, freelancers, contractors, professional advice
- **Travel**: Business trips, flights, hotels, transportation for business purposes
- **Meals/Entertainment**: Business meals, client entertainment, team events
- **Equipment**: Hardware, machinery, computers, office equipment
- **Rent/Utilities**: Office rent, utilities, internet, phone services
- **Insurance**: Business insurance policies
- **Education/Training**: Courses, training programs, certifications for business
- **Transportation**: Business vehicle expenses, fuel, parking, business travel
- **Legal/Accounting**: Legal services, accounting services, tax preparation
- **Telecommunications**: Phone services, internet, communication tools
- **Bank Fees**: Banking fees, transaction fees, account maintenance
- **Uncategorized**: Expenses that don't fit other categories

## Categorization Guidelines

### Software/Subscriptions
Include:
- SaaS platforms (CRM, project management, collaboration tools)
- Cloud services (hosting, storage, infrastructure)
- Software licenses and subscriptions
- Online tools and platforms
- API services and integrations
- Development tools and services
- Analytics and tracking tools
- Email marketing platforms
- Payment processing services
- Domain and hosting services

Examples:
- "Twilio" → Software/Subscriptions (cloud communications)
- "GoDaddy" → Software/Subscriptions (domain/hosting) or Rent/Utilities
- "OpenAI" → Software/Subscriptions (AI services)
- "Calendly" → Software/Subscriptions (scheduling tool)
- "ClickUp" → Software/Subscriptions (project management)
- "Cloudflare" → Software/Subscriptions (CDN/hosting services)

### Marketing/Advertising
Include:
- Social media advertising (Facebook Ads, Google Ads, etc.)
- Marketing automation platforms
- SEO tools and services
- Content creation tools
- Email marketing services
- Analytics and conversion tracking tools
- Influencer marketing platforms

Examples:
- "Facebook Ads" → Marketing/Advertising
- "Google Ads" → Marketing/Advertising
- "Mailchimp" → Marketing/Advertising (email marketing)
- "Ahrefs" → Marketing/Advertising (SEO tool)

### Professional Services
Include:
- Freelance platforms (Upwork, Fiverr)
- Consulting services
- Design services
- Development services
- Writing and content services
- Virtual assistants

Examples:
- "Upwork" → Professional Services
- Consulting fees → Professional Services

### Rent/Utilities
Include:
- Office rent
- Internet and phone services
- Cloud infrastructure (if primary business infrastructure)
- Co-working spaces
- Utilities (electricity, water, etc.)

Examples:
- "Google Workspace" → Rent/Utilities (business email/infrastructure)
- "Microsoft 365" → Rent/Utilities (business productivity suite)
- Office rent → Rent/Utilities

### Telecommunications
Include:
- Phone services
- Internet services
- Communication tools (if not covered under Software/Subscriptions)
- Video conferencing (if primary communication tool)

### Education/Training
Include:
- Online courses for business skills
- Training programs
- Certifications
- Educational platforms for business development

Examples:
- "Coursera" (business courses) → Education/Training
- "Udemy" (business courses) → Education/Training

## Important Notes

1. **Online Services are Business Expenses**: Many modern businesses operate primarily online. Services like cloud hosting, SaaS tools, and digital platforms are legitimate business expenses, not personal entertainment.

2. **Context Matters**: Consider the business context. For example:
   - "Twilio" for a business → Software/Subscriptions (communication infrastructure)
   - "Netflix" for a business → Likely Meals/Entertainment (if for team) or may need clarification

3. **Subscription Services**: Most recurring online services should go to Software/Subscriptions unless they're clearly in another category (e.g., marketing tools → Marketing/Advertising).

4. **When in Doubt**: If an expense could fit multiple categories, choose the most specific one. If truly unclear, use "Uncategorized" and note why.

## Output Format

When categorizing a transaction, provide:
1. **Category**: The selected category name
2. **Reasoning**: Brief explanation of why this category was chosen
3. **Business Context**: Note if it's an online service, subscription, or traditional business expense

Example:
```
Category: Software/Subscriptions
Reasoning: Twilio provides cloud-based communication APIs and services, which are essential infrastructure for modern businesses. This is a recurring subscription service for business operations.
Business Context: Online service subscription
```

