// Test IDs for the auth feature (login, register, password reset, logout).
// Add new keys here as you wire up additional auth UI; see ./index.js for
// the recipe to add a new feature file.
//
// Directive:
//   - Keys are camelCase, values are kebab-case shaped as `<feature>-<element>`
//     (or `<feature>-<element>-<qualifier>` when an element repeats). Examples:
//     'login-submit-button', 'cart-quantity-input', 'product-card-image'.
//   - Reference them in JSX as `data-testid={LOGIN.submitButton}`.
//
// Why kebab-case values: required by qabot's CSS-attribute selector matcher
// and the lint rule `emergent(kebab-case-testid)`.

export const LOGIN = {
	emailInput: 'login-email-input',
	passwordInput: 'login-password-input',
	submitButton: 'login-submit-button',
	forgotPasswordLink: 'login-forgot-password-link',
	googleButton: 'login-google-button',
	registerLink: 'login-register-link',
	formError: 'login-form-error',
};

export const FORGOT_PASSWORD = {
	emailInput: 'forgot-password-email-input',
	submitButton: 'forgot-password-submit-button',
	sentPanel: 'forgot-password-sent-panel',
	backLink: 'forgot-password-back-link',
	returnLink: 'forgot-password-return-link',
	emailError: 'forgot-password-email-error',
};

export const RESET_PASSWORD = {
	newInput: 'reset-password-new-input',
	confirmInput: 'reset-password-confirm-input',
	submitButton: 'reset-password-submit-button',
	newError: 'reset-password-new-error',
	confirmError: 'reset-password-confirm-error',
	formError: 'reset-password-form-error',
	missingToken: 'reset-password-missing-token',
	requestNewLink: 'reset-password-request-new-link',
	backLink: 'reset-password-back-link',
};

export const REGISTER = {
	nameInput: 'register-name-input',
	emailInput: 'register-email-input',
	passwordInput: 'register-password-input',
	passwordConfirmInput: 'register-password-confirm-input',
	submitButton: 'register-submit-button',
	loginLink: 'register-login-link',
};

export const LOGOUT = {
	button: 'logout-button',
};
