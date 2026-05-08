/**
 * Email Configuration
 * 
 * TEMPORARY: Email features are disabled while Resend domain verification is pending.
 * Set EMAIL_ENABLED to true once the domain is verified and email service is ready.
 * 
 * All email-related settings and database entries are preserved.
 * Simply change this flag to re-enable email functionality.
 */

export const EMAIL_CONFIG = {
  // Set to true to enable email features, false to disable
  EMAIL_ENABLED: false,
  
  // Message shown when email is disabled
  DISABLED_MESSAGE: 'Email service is temporarily unavailable. Please try again later.',
  
  // Tooltip message for disabled email buttons
  DISABLED_TOOLTIP: 'Email service temporarily disabled - domain verification in progress'
};

export default EMAIL_CONFIG;
