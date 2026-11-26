# Money

- Amounts cross the API as decimal strings with exactly two fraction digits.
- Storage is TEXT; arithmetic goes through `ledgerline.money`.
- Rounding is half-even, applied once at the boundary.
- An invoice has one currency. Payments and refunds inherit it.
- Refunds on a payment never exceed the captured amount.
