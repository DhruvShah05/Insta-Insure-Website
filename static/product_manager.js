/**
 * Product Manager - Local Storage Utility for Insurance Product Names
 * Manages product names locally on the PC without storing in database
 */

class ProductManager {
    constructor() {
        this.storageKey = 'insurance_product_names';
        this.defaultProducts = [
            'HEALTH INSURANCE',
            'MOTOR INSURANCE', 
            'FACTORY INSURANCE',
            'LIFE INSURANCE',
            'TRAVEL INSURANCE',
            'BHARAT GRIHA RAKSHA',
            'BHARAT SOOKSHMA UDYAM SURAKSHA',
            'BHARAT LAGHU UDYAM SURAKSHA',
            'BHARAT GRIHA RAKSHA POLICY - LTD'
        ];
    }

    /**
     * Get all product names from local storage
     */
    getProducts() {
        try {
            const stored = localStorage.getItem(this.storageKey);
            if (stored) {
                const products = JSON.parse(stored);
                return [...new Set([...this.defaultProducts, ...products])].sort();
            }
            return this.defaultProducts;
        } catch (error) {
            console.error('Error loading products:', error);
            return this.defaultProducts;
        }
    }

    /**
     * Add a new product name to local storage
     */
    addProduct(productName) {
        if (!productName || typeof productName !== 'string') {
            return false;
        }

        const trimmed = productName.trim().toUpperCase();
        if (trimmed.length === 0) {
            return false;
        }

        try {
            const products = this.getProducts();
            if (!products.includes(trimmed)) {
                const stored = localStorage.getItem(this.storageKey);
                const existing = stored ? JSON.parse(stored) : [];
                existing.push(trimmed);
                localStorage.setItem(this.storageKey, JSON.stringify(existing));
                return true;
            }
            return false; // Already exists
        } catch (error) {
            console.error('Error saving product:', error);
            return false;
        }
    }

    /**
     * Remove a product name from local storage
     */
    removeProduct(productName) {
        if (!productName) return false;

        const trimmed = productName.trim().toUpperCase();
        
        // Don't allow removal of default products
        if (this.defaultProducts.includes(trimmed)) {
            return false;
        }

        try {
            const stored = localStorage.getItem(this.storageKey);
            if (stored) {
                const products = JSON.parse(stored);
                const filtered = products.filter(p => p !== trimmed);
                localStorage.setItem(this.storageKey, JSON.stringify(filtered));
                return true;
            }
            return false;
        } catch (error) {
            console.error('Error removing product:', error);
            return false;
        }
    }

    /**
     * Check if a product requires additional fields
     */
    requiresAdditionalFields(productName) {
        if (!productName) return false;
        
        const trimmed = productName.trim().toUpperCase();
        return trimmed.includes('HEALTH') || 
               trimmed.includes('FACTORY') ||
               trimmed.includes('BHARAT GRIHA RAKSHA') ||
               trimmed.includes('BHARAT SOOKSHMA UDYAM SURAKSHA') ||
               trimmed.includes('BHARAT LAGHU UDYAM SURAKSHA');
    }

    /**
     * Get the type of additional fields required
     */
    getAdditionalFieldsType(productName) {
        if (!productName) return null;
        
        const trimmed = productName.trim().toUpperCase();
        if (trimmed.includes('HEALTH')) {
            return 'health';
        } else if (trimmed.includes('FACTORY') || 
                   trimmed.includes('BHARAT GRIHA RAKSHA') ||
                   trimmed.includes('BHARAT SOOKSHMA UDYAM SURAKSHA') ||
                   trimmed.includes('BHARAT LAGHU UDYAM SURAKSHA')) {
            return 'factory';
        }
        return null;
    }

    /**
     * Populate a select element with product options
     */
    populateSelect(selectElement, selectedValue = '') {
        if (!selectElement) return;

        const products = this.getProducts();
        
        // Clear existing options except placeholder
        selectElement.innerHTML = '<option value="">Select product type...</option>';
        
        // Add products
        products.forEach(product => {
            const option = document.createElement('option');
            option.value = product;
            option.textContent = product;
            if (product === selectedValue) {
                option.selected = true;
            }
            selectElement.appendChild(option);
        });

        // Add "Add New" option
        const addNewOption = document.createElement('option');
        addNewOption.value = '__ADD_NEW__';
        addNewOption.textContent = '+ Add New Product Type';
        addNewOption.style.fontStyle = 'italic';
        addNewOption.style.color = '#666';
        selectElement.appendChild(addNewOption);
    }

    /**
     * Handle "Add New" selection in dropdown
     */
    handleAddNewSelection(selectElement, callback) {
        if (!selectElement) return;

        selectElement.addEventListener('change', (e) => {
            if (e.target.value === '__ADD_NEW__') {
                const newProduct = prompt('Enter new product type:');
                if (newProduct) {
                    const added = this.addProduct(newProduct);
                    if (added) {
                        // Repopulate the select with new product selected
                        this.populateSelect(selectElement, newProduct.trim().toUpperCase());
                        if (callback) callback(newProduct.trim().toUpperCase());
                    } else {
                        alert('Product already exists or invalid name');
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

// Create global instance
window.productManager = new ProductManager();

/**
 * Initialize product dropdown for a form
 */
function initializeProductDropdown(selectId, onChangeCallback) {
    const selectElement = document.getElementById(selectId);
    if (!selectElement) {
        console.error(`Product select element with ID '${selectId}' not found`);
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
        selectElement = newSelect;
    }

    // Populate and setup event handlers
    window.productManager.populateSelect(selectElement);
    window.productManager.handleAddNewSelection(selectElement, onChangeCallback);
    
    return selectElement;
}
