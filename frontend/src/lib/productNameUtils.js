/**
 * Utility functions for cleaning product names
 * Removes "None" patterns that can occur from null values in database
 */

/**
 * Clean None patterns from strings
 * Handles: NonexNone, NoneXNone, xNone, (None), None Kg, etc.
 */
export const cleanNonePatterns = (str) => {
  if (!str) return '';
  return str
    .replace(/\s*NonexNone\s*/gi, ' ')
    .replace(/\s*NoneXNone\s*/gi, ' ')
    .replace(/\s*None\s*x\s*None\s*/gi, ' ')
    .replace(/\s*xNone\s*/gi, ' ')
    .replace(/\s*Nonex\s*/gi, ' ')
    .replace(/\s*\(None\)\s*/gi, ' ')
    .replace(/\s*\(None\d*[Kk]?g?\)\s*/gi, ' ')
    .replace(/\s*None\s*[Kk]g\s*/gi, ' ')
    .replace(/\s+None\s*$/gi, '')
    .replace(/^\s*None\s+/gi, '')
    .replace(/\s+/g, ' ')
    .trim();
};

/**
 * Check if a value is valid (not None, null, undefined, or empty)
 */
export const isValidValue = (val) => {
  if (!val) return false;
  if (typeof val !== 'string') return true;
  const lower = val.toLowerCase().trim();
  return lower !== 'none' && lower !== 'null' && lower !== 'undefined' && lower !== '';
};

/**
 * Clean product name - removes None patterns and normalizes spacing
 */
export const cleanProductName = (name) => {
  return cleanNonePatterns(name);
};

export default {
  cleanNonePatterns,
  isValidValue,
  cleanProductName
};
