// content.js
(async function () {
    console.log("📡 REPLICA Extension loaded on:", window.location.href);
    
    // Create overlay function
    function createSecurityOverlay() {
        // Create an overlay that blocks the entire page initially
        const overlay = document.createElement('div');
        overlay.id = 'replica-security-overlay';
        overlay.style.position = 'fixed';
        overlay.style.top = '0';
        overlay.style.left = '0';
        overlay.style.width = '100%';
        overlay.style.height = '100%';
        overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.8)';
        overlay.style.zIndex = '9999999';
        overlay.style.display = 'flex';
        overlay.style.flexDirection = 'column';
        overlay.style.justifyContent = 'center';
        overlay.style.alignItems = 'center';
        overlay.style.color = 'white';
        overlay.style.fontFamily = 'Arial, sans-serif';
        
        const loadingMessage = document.createElement('div');
        loadingMessage.textContent = 'Checking website security...';
        loadingMessage.style.fontSize = '24px';
        loadingMessage.style.marginBottom = '20px';
        
        const spinner = document.createElement('div');
        spinner.style.border = '5px solid #f3f3f3';
        spinner.style.borderTop = '5px solid #3498db';
        spinner.style.borderRadius = '50%';
        spinner.style.width = '50px';
        spinner.style.height = '50px';
        spinner.style.animation = 'spin 2s linear infinite';
        
        // Add the spinner animation
        const style = document.createElement('style');
        style.textContent = `
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        `;
        
        document.head.appendChild(style);
        overlay.appendChild(loadingMessage);
        overlay.appendChild(spinner);
        
        return overlay;
    }
    
    // Helper function to remove overlay with a message
    function removeOverlayWithMessage(overlay, message, color, duration) {
        if (overlay) {
            overlay.innerHTML = ''; // Clear existing content
            
            const statusIcon = document.createElement('div');
            statusIcon.innerHTML = color === 'green' ? '✅' : '⚠️';
            statusIcon.style.fontSize = '60px';
            statusIcon.style.marginBottom = '20px';
            
            const statusMessage = document.createElement('div');
            statusMessage.textContent = message;
            statusMessage.style.fontSize = '24px';
            statusMessage.style.color = color;
            
            overlay.appendChild(statusIcon);
            overlay.appendChild(statusMessage);
            
            // Remove the overlay after the specified duration
            setTimeout(() => {
                overlay.remove();
            }, duration);
        }
    }
    
    // Local check for known phishing domains before server check
    function checkKnownPhishingSites(url) {
        const knownPhishingSites = {
            'goog1e-login.com': {
                isFake: true,
                redirect: 'https://www.google.com',
                message: 'This appears to be a phishing site mimicking Google. Would you like to go to the real site instead?'
            },
            'amazon-secure-payment.com': {
                isFake: true,
                redirect: 'https://www.amazon.com',
                message: 'This appears to be a phishing site mimicking Amazon. Would you like to go to the real site instead?'
            },
            'faceboook-verification.com': {
                isFake: true,
                redirect: 'https://www.facebook.com',
                message: 'This appears to be a phishing site mimicking Facebook. Would you like to go to the real site instead?'
            },
            'tw1tter-security.com': {
                isFake: true,
                redirect: 'https://www.twitter.com',
                message: 'This appears to be a phishing site mimicking Twitter. Would you like to go to the real site instead?'
            }
        };
        
        // Extract domain from URL
        let domain;
        try {
            domain = new URL(url).hostname.replace('www.', '');
        } catch (e) {
            console.error("Error parsing URL:", e);
            return null;
        }
        
        // Check if domain is in our list
        if (knownPhishingSites[domain]) {
            console.log("🔒 Known phishing site detected locally:", domain);
            return {
                status: 'fake',
                message: knownPhishingSites[domain].message,
                redirect: knownPhishingSites[domain].redirect
            };
        }
        
        return null;
    }
    
    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeOverlay);
    } else {
        initializeOverlay();
    }
    
    function initializeOverlay() {
        const currentUrl = window.location.href;
        console.log("📡 Checking URL:", currentUrl);
        
        // Create and append the overlay
        const overlay = createSecurityOverlay();
        document.body.appendChild(overlay);
        
        // First check locally for known phishing sites
        const localCheckResult = checkKnownPhishingSites(currentUrl);
        if (localCheckResult) {
            console.log("🔒 Local check result:", localCheckResult);
            handleURLCheckResult(localCheckResult, overlay);
            return;
        }
        
        // If not found locally, check with backend
        chrome.runtime.sendMessage(
            {
                type: 'check_url_authenticated',
                url: currentUrl
            },
            (response) => {
                if (chrome.runtime.lastError) {
                    console.error("Error sending message:", chrome.runtime.lastError);
                    removeOverlayWithMessage(overlay, "Error checking website security. Proceeding...", "orange", 3000);
                    return;
                }

                console.log("✅ Backend URL check result:", response);
                handleURLCheckResult(response, overlay);
            }
        );
    }
    
    function handleURLCheckResult(response, overlay) {
        if (response.status === "fake") {
            // For fake websites, show warning and provide options
            overlay.innerHTML = ''; // Clear existing content
            
            const warningIcon = document.createElement('div');
            warningIcon.innerHTML = '⚠️';
            warningIcon.style.fontSize = '60px';
            warningIcon.style.marginBottom = '20px';
            
            const warningMessage = document.createElement('div');
            warningMessage.textContent = response.message || 'This website appears to be fake!';
            warningMessage.style.fontSize = '24px';
            warningMessage.style.marginBottom = '30px';
            warningMessage.style.textAlign = 'center';
            warningMessage.style.maxWidth = '80%';
            
            const buttonContainer = document.createElement('div');
            buttonContainer.style.display = 'flex';
            buttonContainer.style.gap = '20px';
            
            // Create go to safe site button
            if (response.redirect) {
                const safeButton = document.createElement('button');
                safeButton.textContent = 'Go to Safe Site';
                safeButton.style.padding = '12px 24px';
                safeButton.style.backgroundColor = '#2ecc71';
                safeButton.style.border = 'none';
                safeButton.style.borderRadius = '5px';
                safeButton.style.color = 'white';
                safeButton.style.fontSize = '16px';
                safeButton.style.cursor = 'pointer';
                safeButton.onclick = () => {
                    window.location.href = response.redirect;
                };
                buttonContainer.appendChild(safeButton);
            }
            
            // Create continue anyway button
            const continueButton = document.createElement('button');
            continueButton.textContent = 'Continue Anyway';
            continueButton.style.padding = '12px 24px';
            continueButton.style.backgroundColor = '#e74c3c';
            continueButton.style.border = 'none';
            continueButton.style.borderRadius = '5px';
            continueButton.style.color = 'white';
            continueButton.style.fontSize = '16px';
            continueButton.style.cursor = 'pointer';
            continueButton.onclick = () => {
                overlay.remove();
            };
            buttonContainer.appendChild(continueButton);
            
            overlay.appendChild(warningIcon);
            overlay.appendChild(warningMessage);
            overlay.appendChild(buttonContainer);
            
        } else { // This will include "legitimate" and any errors
            // For legitimate websites, briefly show confirmation and remove overlay
            removeOverlayWithMessage(overlay, response.message || 'This website appears to be legitimate!', 'green', 2000);
        }
    }
})();

// Simple message to check if background script is responsive
chrome.runtime.sendMessage({ message: 'Hello from content script!' }, (response) => {
    if (chrome.runtime.lastError) {
        console.error("Error sending message:", chrome.runtime.lastError);
        return;
    }
    console.log('Response from background script:', response);
});