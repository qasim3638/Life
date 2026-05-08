// Currency formatter utility
export const formatCurrency = (amount) => {
  return `£${Number(amount).toFixed(2)}`;
};

export const CURRENCY_SYMBOL = '£';
export const CURRENCY_NAME = 'GBP';
