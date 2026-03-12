document.addEventListener('DOMContentLoaded', () => {
  const toggleButton = document.getElementById('toggle');
  if (!toggleButton) {
      console.error("Toggle button element not found.");
      return;
  }

  const updateButtonText = (enableOption) => {
      toggleButton.textContent = enableOption ? 'Disable URL Checking' : 'Enable URL Checking';
      if (enableOption) {
          toggleButton.classList.remove('disable');
      } else {
          toggleButton.classList.add('disable');
      }
  };

  const handleToggleClick = () => {
      chrome.storage.local.get('enableOption', (data) => {
          const enableOption = !data.enableOption;
          chrome.storage.local.set({ enableOption: enableOption }, () => {
              updateButtonText(enableOption);
              chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
                  if (tabs && tabs.length > 0) {
                      chrome.tabs.sendMessage(tabs[0].id, { type: 'update_enable_option', enableOption: enableOption });
                  } else {
                      console.warn("No active tabs found.");
                  }
              });
          });
      });
  };

  const initializeButtonState = () => {
      chrome.storage.local.get('enableOption', (data) => {
          const enableOption = data.enableOption ?? false;
          updateButtonText(enableOption);
      });
  };

  toggleButton.addEventListener('click', handleToggleClick);
  initializeButtonState();
});