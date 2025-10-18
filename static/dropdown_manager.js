/**
 * Dropdown Manager - Local Storage Utility for Insurance Companies and Agent Names
 * Manages dropdown lists locally on the PC without storing in database
 */

class DropdownManager {
    constructor(storageKey, defaultItems = []) {
        this.storageKey = storageKey;
        this.defaultItems = defaultItems;
    }

    /**
     * Get all items from local storage
     */
    getItems() {
        try {
            const stored = localStorage.getItem(this.storageKey);
            if (stored) {
                const items = JSON.parse(stored);
                return [...new Set([...this.defaultItems, ...items])].sort();
            }
            return this.defaultItems;
        } catch (error) {
            console.error(`Error loading items for ${this.storageKey}:`, error);
            return this.defaultItems;
        }
    }

    /**
     * Add a new item to local storage
     */
    addItem(itemName) {
        if (!itemName || typeof itemName !== 'string') {
            return false;
        }

        const trimmed = itemName.trim();
        if (trimmed.length === 0) {
            return false;
        }

        try {
            const items = this.getItems();
            if (!items.includes(trimmed)) {
                const stored = localStorage.getItem(this.storageKey);
                const existing = stored ? JSON.parse(stored) : [];
                existing.push(trimmed);
                localStorage.setItem(this.storageKey, JSON.stringify(existing));
                return true;
            }
            return false; // Already exists
        } catch (error) {
            console.error(`Error saving item for ${this.storageKey}:`, error);
            return false;
        }
    }

    /**
     * Remove an item from local storage
     */
    removeItem(itemName) {
        if (!itemName) return false;

        const trimmed = itemName.trim();
        
        // Don't allow removal of default items
        if (this.defaultItems.includes(trimmed)) {
            return false;
        }

        try {
            const stored = localStorage.getItem(this.storageKey);
            if (stored) {
                const items = JSON.parse(stored);
                const filtered = items.filter(item => item !== trimmed);
                localStorage.setItem(this.storageKey, JSON.stringify(filtered));
                return true;
            }
            return false;
        } catch (error) {
            console.error(`Error removing item for ${this.storageKey}:`, error);
            return false;
        }
    }

    /**
     * Populate a select element with options
     */
    populateSelect(selectElement, selectedValue = '', placeholder = 'Select...') {
        if (!selectElement) return;

        const items = this.getItems();
        
        // Clear existing options except placeholder
        selectElement.innerHTML = `<option value="">${placeholder}</option>`;
        
        // Add items
        items.forEach(item => {
            const option = document.createElement('option');
            option.value = item;
            option.textContent = item;
            if (item === selectedValue) {
                option.selected = true;
            }
            selectElement.appendChild(option);
        });

        // Add "Add New" option
        const addNewOption = document.createElement('option');
        addNewOption.value = '__ADD_NEW__';
        addNewOption.textContent = '+ Add New';
        addNewOption.style.fontStyle = 'italic';
        addNewOption.style.color = '#666';
        selectElement.appendChild(addNewOption);
    }

    /**
     * Handle "Add New" selection in dropdown
     */
    handleAddNewSelection(selectElement, callback, promptText = 'Enter new item:') {
        if (!selectElement) return;

        selectElement.addEventListener('change', (e) => {
            if (e.target.value === '__ADD_NEW__') {
                const newItem = prompt(promptText);
                if (newItem) {
                    const added = this.addItem(newItem);
                    if (added) {
                        // Repopulate the select with new item selected
                        this.populateSelect(selectElement, newItem.trim(), selectElement.querySelector('option').textContent);
                        if (callback) callback(newItem.trim());
                    } else {
                        alert('Item already exists or invalid name');
                        selectElement.value = ''; // Reset selection
                    }
                } else {
                    selectElement.value = ''; // Reset selection if cancelled
                }
            } else if (callback) {
                callback(e.target.value);
            }
        });
    }
}

// Create managers for insurance companies and agent names
window.insuranceCompanyManager = new DropdownManager('insurance_companies', [
    'Bajaj General Insurance Limited',
    'Tata AIG General Insurance Co Ltd',
    'ICICI Lombard General Insurance Co Ltd',
    'Generali Central Insurance Co Ltd',
    'The Oriental Insurance Co Ltd',
    'United India Insurance Co Ltd',
    'HDFC Ergo General Insurance Co Ltd',
    'Go Digit'
]);

window.agentNameManager = new DropdownManager('agent_names', [
    'Sameer Shah',
    'Sweta Shah',
    'Dhruv Shah',
    'Vikas Mhatre',
    'Fortune Five',
    'Jaimini Thakkar',
    'C.H.Ramchandani'
]);

/**
 * Initialize insurance company dropdown
 */
function initializeInsuranceCompanyDropdown(selectId, onChangeCallback) {
    const selectElement = document.getElementById(selectId);
    if (!selectElement) {
        console.error(`Insurance company select element with ID '${selectId}' not found`);
        return;
    }

    // Convert input to select if needed
    if (selectElement.tagName.toLowerCase() === 'input') {
        const newSelect = document.createElement('select');
        newSelect.id = selectElement.id;
        newSelect.name = selectElement.name;
        newSelect.className = selectElement.className;
        newSelect.required = selectElement.required;
        
        // Copy attributes
        Array.from(selectElement.attributes).forEach(attr => {
            if (!['type', 'placeholder'].includes(attr.name)) {
                newSelect.setAttribute(attr.name, attr.value);
            }
        });
        
        selectElement.parentNode.replaceChild(newSelect, selectElement);
    }

    const finalSelectElement = document.getElementById(selectId);
    
    // Populate and setup event handlers
    window.insuranceCompanyManager.populateSelect(finalSelectElement, '', 'Select insurance company...');
    window.insuranceCompanyManager.handleAddNewSelection(finalSelectElement, onChangeCallback, 'Enter new insurance company name:');
    
    return finalSelectElement;
}

/**
 * Initialize agent name dropdown
 */
function initializeAgentNameDropdown(selectId, onChangeCallback) {
    const selectElement = document.getElementById(selectId);
    if (!selectElement) {
        console.error(`Agent name select element with ID '${selectId}' not found`);
        return;
    }

    // Convert input to select if needed
    if (selectElement.tagName.toLowerCase() === 'input') {
        const newSelect = document.createElement('select');
        newSelect.id = selectElement.id;
        newSelect.name = selectElement.name;
        newSelect.className = selectElement.className;
        newSelect.required = selectElement.required;
        
        // Copy attributes
        Array.from(selectElement.attributes).forEach(attr => {
            if (!['type', 'placeholder'].includes(attr.name)) {
                newSelect.setAttribute(attr.name, attr.value);
            }
        });
        
        selectElement.parentNode.replaceChild(newSelect, selectElement);
    }

    const finalSelectElement = document.getElementById(selectId);
    
    // Populate and setup event handlers
    window.agentNameManager.populateSelect(finalSelectElement, '', 'Select agent name...');
    window.agentNameManager.handleAddNewSelection(finalSelectElement, onChangeCallback, 'Enter new agent name:');
    
    return finalSelectElement;
}
