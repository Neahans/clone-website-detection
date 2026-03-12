// background.js
// Define the backend URL in one place for easier configuration
const BACKEND_URL = "http://127.0.0.1:5000";
// Uncomment this line in production:
// const BACKEND_URL = "https://replica-453220.el.r.appspot.com";

// Known phishing URLs mapping to legitimate sites
const url_mapping = {
    'http://goog1e-login.com': 'https://www.google.com',
    'http://amazon-secure-payment.com': 'https://www.amazon.com',
    'http://faceboook-verification.com': 'https://www.facebook.com',
    'http://tw1tter-security.com': 'https://www.twitter.com',
    'http://bankofamerica-login-secure.com': 'https://www.bankofamerica.com',
    'http://paypal-security-check.com': 'https://www.paypal.com',
    'http://microsoft-support-online.com': 'https://www.microsoft.com',
    'http://apple-id-verification.com': 'https://www.apple.com',
    'http://netflix-billing-update.com': 'https://www.netflix.com',
    'http://linkedin-job-alert.com': 'https://www.linkedin.com'
};

// Helper function for checking URLs
function checkUrl(url, tabId) {
    console.log("🔍 Background script checking URL:", url);
    
    // Skip chrome:// URLs and other browser internal pages
    if (url.startsWith('chrome://') || 
        url.startsWith('chrome-extension://') || 
        url.startsWith('about:') ||
        url.startsWith('edge://') ||
        url.startsWith('brave://')) {
        return Promise.resolve({
            status: 'safe',
            message: 'Internal browser page. Safe to proceed.'
        });
    }

    // First check in our local database of known phishing sites
    for (const knownUrl in url_mapping) {
        if (url.includes(new URL(knownUrl).hostname)) {
            console.log("🚨 Found in local phishing database:", url);
            
            return Promise.resolve({
                status: 'fake',
                message: `This appears to be a phishing site mimicking a legitimate website. Redirecting you to the real site.`,
                redirect: url_mapping[knownUrl]
            });
        }
    }

    // If not found locally, check with backend
    return fetch(`${BACKEND_URL}/check_url?url=${encodeURIComponent(url)}`, {
        method: 'GET',
        credentials: 'include',
        headers: getAuthHeaders()
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log("✅ Received response from backend:", data);
        
        // Update message for automatic redirect
        if (data.status === 'fake' && data.redirect) {
            data.message = data.message.replace('Would you like to go to the real site instead?', 'Redirecting you to the real site.');
        }
        return data; // Return the data
    })
    .catch(error => {
        console.error("❌ Error connecting to backend:", error);
        
        return {
            status: "error",
            message: "Error checking website security. Proceeding with caution.",
            details: error.message
        };
    });
}

// Function to get auth headers if token is available
function getAuthHeaders() {
    const headers = {
        'Content-Type': 'application/json'
    };
    
    // Add auth token if available
    chrome.storage.local.get(['authToken'], function(result) {
        if (result.authToken) {
            headers['Authorization'] = `Bearer ${result.authToken}`;
        }
    });
    
    return headers;
}

// Function to fetch history from the server
function fetchHistory() {
    return new Promise((resolve, reject) => {
        chrome.storage.local.get(['authToken'], function(result) {
            const headers = {};
            if (result.authToken) {
                headers['Authorization'] = `Bearer ${result.authToken}`;
            }
            
            fetch(`${BACKEND_URL}/history`, {
                method: 'GET',
                credentials: 'include',
                headers: headers
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log("✅ Received history from backend:", data);
                resolve(data.history || []);
            })
            .catch(error => {
                console.error("❌ Error fetching history:", error);
                reject(error);
            });
        });
    });
}

// Function to clear history on the server
function clearHistory() {
    return new Promise((resolve, reject) => {
        chrome.storage.local.get(['authToken'], function(result) {
            const headers = {
                'Content-Type': 'application/json'
            };
            
            if (result.authToken) {
                headers['Authorization'] = `Bearer ${result.authToken}`;
            }
            
            fetch(`${BACKEND_URL}/clear_history`, {
                method: 'POST',
                credentials: 'include',
                headers: headers
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log("✅ History cleared:", data);
                resolve(data);
            })
            .catch(error => {
                console.error("❌ Error clearing history:", error);
                reject(error);
            });
        });
    });
}

// Listen for messages from content scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    console.log("📩 Background script received message:", message);

    if (message.type === 'check_url_authenticated') {
        checkUrl(message.url, sender.tab?.id)
            .then(data => {
                console.log("Sending response back to content script:", data);
                sendResponse(data);
            })
            .catch(error => {
                console.error("Error in checkUrl:", error);
                sendResponse({
                    status: "error",
                    message: "Error checking URL security",
                    details: error.message
                });
            });

        return true; // Keep the message channel open for async response
    }
    
    // Handle history requests
    if (message.type === 'get_history') {
        fetchHistory()
            .then(history => {
                sendResponse({
                    success: true,
                    history: history
                });
            })
            .catch(error => {
                sendResponse({
                    success: false,
                    error: error.message,
                    history: []
                });
            });
        return true; // Keep the message channel open for async response
    }
    
    // Handle clear history requests
    if (message.type === 'clear_history') {
        clearHistory()
            .then(result => {
                sendResponse({
                    success: true,
                    message: result.message
                });
            })
            .catch(error => {
                sendResponse({
                    success: false,
                    error: error.message
                });
            });
        return true; // Keep the message channel open for async response
    }

    // Handle general messages
    if (message.message) {
        console.log("Received general message:", message.message);
        sendResponse({ status: "received", message: "Message received by background script" });
        return true;
    }
});

// Listen for tab updates with webNavigation for better control
chrome.webNavigation.onCommitted.addListener((details) => {
    // Only run for main frame, not iframes
    if (details.frameId === 0) {
        console.log("Navigation committed to:", details.url);
        // The content script will handle the blocking and user interaction
    }
});

// Store auth token
let authToken = null;

// Add a function to get user data using the stored token
function getUserData() {
    return new Promise((resolve, reject) => {
        chrome.storage.local.get(['authToken'], function(result) {
            if (result.authToken) {
                authToken = result.authToken;

                fetch(`${BACKEND_URL}/user`, {
                    method: 'GET',
                    headers: {
                        'Authorization': `Bearer ${authToken}`
                    }
                })
                .then(response => response.json())
                .then(data => resolve(data))
                .catch(error => reject(error));
            } else {
                resolve({ user: null });
            }
        });
    });
}

// This event is fired when a navigation is completed
chrome.webNavigation.onCompleted.addListener((details) => {
    if (details.frameId === 0) {
        checkUrl(details.url, details.tabId)
            .then(data => {
                console.log("URL check completed:", data);
                // All history is now saved server-side via the check_url endpoint
            })
            .catch(error => {
                console.error("Error in checkUrl:", error);
            });
    }
});

// Initialize the extension on install
chrome.runtime.onInstalled.addListener(function(details) {
    if (details.reason === "install") {
        console.log("REPLICA Extension installed!");
        
        // Set initial state
        chrome.storage.local.set({
            enableStatus: true
        });
    }
});

// Log when background script initializes
console.log("🚀 REPLICA Background Script initialized!");
