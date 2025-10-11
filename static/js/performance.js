/**
 * Performance Optimization Script for Insurance Portal
 * Optimized for multi-user concurrent access
 */

// Performance monitoring
const performanceMonitor = {
    startTime: performance.now(),
    metrics: {},
    
    // Track page load performance
    trackPageLoad() {
        window.addEventListener('load', () => {
            const loadTime = performance.now() - this.startTime;
            this.metrics.pageLoadTime = loadTime;
            console.log(`Page loaded in ${loadTime.toFixed(2)}ms`);
            
            // Send to server if needed (optional)
            if (loadTime > 3000) {
                console.warn('Slow page load detected:', loadTime);
            }
        });
    },
    
    // Track AJAX request performance
    trackAjaxPerformance() {
        const originalFetch = window.fetch;
        window.fetch = function(...args) {
            const startTime = performance.now();
            return originalFetch.apply(this, args).then(response => {
                const endTime = performance.now();
                const duration = endTime - startTime;
                console.log(`API call to ${args[0]} took ${duration.toFixed(2)}ms`);
                return response;
            });
        };
    }
};

// Request queue for handling concurrent requests
const requestQueue = {
    activeRequests: new Map(),
    maxConcurrentRequests: 5,
    
    // Add request to queue with deduplication
    async enqueue(url, options = {}) {
        const requestKey = `${options.method || 'GET'}_${url}`;
        
        // If same request is already in progress, return that promise
        if (this.activeRequests.has(requestKey)) {
            console.log('Deduplicating request:', requestKey);
            return this.activeRequests.get(requestKey);
        }
        
        // Wait if too many concurrent requests
        while (this.activeRequests.size >= this.maxConcurrentRequests) {
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        
        // Create and track the request
        const requestPromise = fetch(url, options)
            .finally(() => {
                this.activeRequests.delete(requestKey);
            });
        
        this.activeRequests.set(requestKey, requestPromise);
        return requestPromise;
    }
};

// Optimized form submission
function optimizedFormSubmit(formElement, options = {}) {
    const formData = new FormData(formElement);
    const submitButton = formElement.querySelector('button[type="submit"]');
    
    // Disable button to prevent double submission
    if (submitButton) {
        submitButton.disabled = true;
        const originalText = submitButton.textContent;
        submitButton.textContent = options.loadingText || 'Processing...';
        
        // Re-enable after timeout as fallback
        setTimeout(() => {
            submitButton.disabled = false;
            submitButton.textContent = originalText;
        }, 30000); // 30 second timeout
    }
    
    // Use request queue for submission
    return requestQueue.enqueue(formElement.action, {
        method: formElement.method || 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    }).then(response => {
        // Re-enable button on completion
        if (submitButton) {
            submitButton.disabled = false;
            submitButton.textContent = originalText;
        }
        return response;
    }).catch(error => {
        // Re-enable button on error
        if (submitButton) {
            submitButton.disabled = false;
            submitButton.textContent = originalText;
        }
        throw error;
    });
}

// Debounced search function
function createDebouncedSearch(searchFunction, delay = 300) {
    let timeoutId;
    return function(...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => searchFunction.apply(this, args), delay);
    };
}

// Lazy loading for images and content
const lazyLoader = {
    observer: null,
    
    init() {
        if ('IntersectionObserver' in window) {
            this.observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        this.loadElement(entry.target);
                        this.observer.unobserve(entry.target);
                    }
                });
            }, {
                rootMargin: '50px'
            });
            
            // Observe all lazy elements
            document.querySelectorAll('[data-lazy]').forEach(el => {
                this.observer.observe(el);
            });
        }
    },
    
    loadElement(element) {
        if (element.dataset.src) {
            element.src = element.dataset.src;
            element.removeAttribute('data-src');
        }
        if (element.dataset.lazy === 'content') {
            // Load content via AJAX if needed
            const url = element.dataset.url;
            if (url) {
                requestQueue.enqueue(url)
                    .then(response => response.text())
                    .then(html => {
                        element.innerHTML = html;
                    });
            }
        }
    }
};

// Cache management for API responses
const apiCache = {
    cache: new Map(),
    maxAge: 5 * 60 * 1000, // 5 minutes
    
    get(key) {
        const item = this.cache.get(key);
        if (item && Date.now() - item.timestamp < this.maxAge) {
            return item.data;
        }
        this.cache.delete(key);
        return null;
    },
    
    set(key, data) {
        this.cache.set(key, {
            data: data,
            timestamp: Date.now()
        });
        
        // Clean old entries
        if (this.cache.size > 100) {
            const oldestKey = this.cache.keys().next().value;
            this.cache.delete(oldestKey);
        }
    }
};

// Optimized API call function
async function cachedApiCall(url, options = {}) {
    const cacheKey = `${options.method || 'GET'}_${url}`;
    
    // Return cached data for GET requests
    if (!options.method || options.method === 'GET') {
        const cached = apiCache.get(cacheKey);
        if (cached) {
            console.log('Returning cached data for:', url);
            return cached;
        }
    }
    
    try {
        const response = await requestQueue.enqueue(url, options);
        const data = await response.json();
        
        // Cache successful GET responses
        if (response.ok && (!options.method || options.method === 'GET')) {
            apiCache.set(cacheKey, data);
        }
        
        return data;
    } catch (error) {
        console.error('API call failed:', url, error);
        throw error;
    }
}

// Initialize performance optimizations
document.addEventListener('DOMContentLoaded', function() {
    // Start performance monitoring
    performanceMonitor.trackPageLoad();
    performanceMonitor.trackAjaxPerformance();
    
    // Initialize lazy loading
    lazyLoader.init();
    
    // Optimize all forms
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function(e) {
            if (form.dataset.optimized !== 'true') {
                e.preventDefault();
                optimizedFormSubmit(form)
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            // Handle success
                            if (data.redirect) {
                                window.location.href = data.redirect;
                            } else if (data.message) {
                                showAlert(data.message, 'success');
                            }
                        } else {
                            showAlert(data.message || 'An error occurred', 'error');
                        }
                    })
                    .catch(error => {
                        console.error('Form submission error:', error);
                        showAlert('Network error. Please try again.', 'error');
                    });
            }
        });
        form.dataset.optimized = 'true';
    });
    
    // Add loading states to buttons
    document.querySelectorAll('button[type="submit"]').forEach(button => {
        button.addEventListener('click', function() {
            if (!button.disabled) {
                button.classList.add('loading');
            }
        });
    });
});

// Export functions for global use
window.performanceOptimizations = {
    cachedApiCall,
    optimizedFormSubmit,
    createDebouncedSearch,
    requestQueue,
    apiCache
};
