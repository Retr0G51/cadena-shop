/**
 * PedidosSaaS - Sistema de JavaScript Principal
 * Este archivo maneja toda la funcionalidad del frontend
 */

// Configuración global
const APP_CONFIG = {
    API_TIMEOUT: 30000,
    NOTIFICATION_DURATION: 3000,
    DEBOUNCE_DELAY: 300,
    MAX_FILE_SIZE: 16 * 1024 * 1024, // 16MB
    ALLOWED_IMAGE_TYPES: ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
};

/**
 * Sistema de manejo de CSRF Token
 */
const CSRF = {
    getToken() {
        const token = document.querySelector('meta[name="csrf-token"]');
        return token ? token.getAttribute('content') : '';
    },
    
    setupAjax() {
        // Configurar fetch global para incluir CSRF token
        const originalFetch = window.fetch;
        window.fetch = function(...args) {
            let [resource, config] = args;
            
            if (config && config.method && config.method.toUpperCase() !== 'GET') {
                config = config || {};
                config.headers = config.headers || {};
                
                if (!config.headers['X-CSRFToken']) {
                    config.headers['X-CSRFToken'] = CSRF.getToken();
                }
            }
            
            return originalFetch(resource, config);
        };
    }
};

/**
 * Sistema de Notificaciones
 */
const Notifications = {
    show(message, type = 'success', duration = APP_CONFIG.NOTIFICATION_DURATION) {
        const notification = document.createElement('div');
        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };
        
        const bgColors = {
            success: 'bg-green-500',
            error: 'bg-red-500',
            warning: 'bg-yellow-500',
            info: 'bg-blue-500'
        };
        
        notification.className = `fixed top-20 right-4 ${bgColors[type]} text-white px-6 py-3 rounded-lg shadow-lg z-50 flex items-center space-x-2 animate-fade-in`;
        notification.innerHTML = `
            <i class="fas ${icons[type]}"></i>
            <span>${message}</span>
            <button onclick="this.parentElement.remove()" class="ml-4 hover:opacity-75">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remover después del tiempo especificado
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transform = 'translateX(100%)';
            setTimeout(() => notification.remove(), 300);
        }, duration);
    },
    
    success(message) {
        this.show(message, 'success');
    },
    
    error(message) {
        this.show(message, 'error');
    },
    
    warning(message) {
        this.show(message, 'warning');
    },
    
    info(message) {
        this.show(message, 'info');
    }
};

/**
 * Sistema de Manejo de Formularios
 */
const FormHandler = {
    /**
     * Deshabilita/habilita un formulario
     */
    setLoading(form, loading = true) {
        const submit = form.querySelector('[type="submit"]');
        const inputs = form.querySelectorAll('input, textarea, select');
        
        if (loading) {
            submit.disabled = true;
            const originalText = submit.textContent;
            submit.dataset.originalText = originalText;
            submit.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Procesando...';
            inputs.forEach(input => input.disabled = true);
        } else {
            submit.disabled = false;
            submit.innerHTML = submit.dataset.originalText || 'Enviar';
            inputs.forEach(input => input.disabled = false);
        }
    },
    
    /**
     * Maneja el envío de formularios vía AJAX
     */
    async handleSubmit(form, options = {}) {
        const {
            onSuccess = () => {},
            onError = () => {},
            showNotification = true
        } = options;
        
        this.setLoading(form, true);
        
        try {
            const formData = new FormData(form);
            const response = await fetch(form.action, {
                method: form.method || 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': CSRF.getToken()
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                if (showNotification) {
                    Notifications.success(data.message || 'Operación exitosa');
                }
                onSuccess(data);
            } else {
                if (showNotification) {
                    Notifications.error(data.message || 'Error al procesar la solicitud');
                }
                onError(data);
            }
        } catch (error) {
            console.error('Error:', error);
            Notifications.error('Error de conexión. Por favor intenta de nuevo.');
        } finally {
            this.setLoading(form, false);
        }
    }
};

/**
 * Sistema de Gestión de Productos
 */
const ProductManager = {
    /**
     * Elimina un producto con confirmación
     */
    async deleteProduct(productId, productName) {
        if (!confirm(`¿Estás seguro de que quieres eliminar "${productName}"?`)) {
            return;
        }
        
        try {
            const response = await fetch(`/dashboard/products/${productId}/delete`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CSRF.getToken()
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                Notifications.success('Producto eliminado exitosamente');
                setTimeout(() => window.location.reload(), 1000);
            } else {
                Notifications.error(data.message || 'Error al eliminar el producto');
            }
        } catch (error) {
            console.error('Error:', error);
            Notifications.error('Error de conexión');
        }
    },
    
    /**
     * Preview de imagen al seleccionar archivo
     */
    setupImagePreview(input, previewElement) {
        input.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file && file.type.startsWith('image/')) {
                // Validar tamaño
                if (file.size > APP_CONFIG.MAX_FILE_SIZE) {
                    Notifications.error('El archivo es muy grande. Máximo 16MB permitido.');
                    input.value = '';
                    return;
                }
                
                // Validar tipo
                if (!APP_CONFIG.ALLOWED_IMAGE_TYPES.includes(file.type)) {
                    Notifications.error('Tipo de archivo no permitido. Solo JPG, PNG, GIF y WebP.');
                    input.value = '';
                    return;
                }
                
                const reader = new FileReader();
                reader.onload = function(e) {
                    previewElement.src = e.target.result;
                    previewElement.style.display = 'block';
                };
                reader.readAsDataURL(file);
            }
        });
    }
};

/**
 * Sistema de Gestión de Pedidos
 */
const OrderManager = {
    /**
     * Actualiza el estado de un pedido
     */
    async updateStatus(orderId, newStatus) {
        try {
            const response = await fetch(`/dashboard/orders/${orderId}/update-status`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CSRF.getToken()
                },
                body: JSON.stringify({ status: newStatus })
            });
            
            const data = await response.json();
            
            if (data.success) {
                Notifications.success(data.message);
                setTimeout(() => window.location.reload(), 1000);
            } else {
                Notifications.error(data.message || 'Error al actualizar el estado');
            }
        } catch (error) {
            console.error('Error:', error);
            Notifications.error('Error de conexión');
        }
    },
    
    /**
     * Imprime un pedido
     */
    printOrder() {
        window.print();
    }
};

/**
 * Sistema de Carrito de Compras
 */
const CartManager = {
    cart: {},
    businessId: null,
    
    /**
     * Inicializa el carrito desde la sesión
     */
    init(businessId, initialCart = {}) {
        this.businessId = businessId;
        this.cart = initialCart;
    },
    
    /**
     * Agrega un producto al carrito
     */
    async addToCart(productId, productInfo) {
        const quantity = parseInt(document.getElementById(`qty-${productId}`).value) || 1;
        
        try {
            const response = await fetch(`/tienda/${productInfo.slug}/add-to-cart`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CSRF.getToken()
                },
                body: JSON.stringify({
                    product_id: productId,
                    quantity: quantity
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Actualizar carrito local
                if (this.cart[productId]) {
                    this.cart[productId].quantity += quantity;
                } else {
                    this.cart[productId] = {
                        id: productId,
                        name: productInfo.name,
                        price: productInfo.price,
                        quantity: quantity,
                        image: productInfo.image
                    };
                }
                
                Notifications.success(data.message);
                this.updateCartUI();
                
                // Reset cantidad
                document.getElementById(`qty-${productId}`).value = 1;
            } else {
                Notifications.error(data.message);
            }
        } catch (error) {
            console.error('Error:', error);
            Notifications.error('Error al agregar al carrito');
        }
    },
    
    /**
     * Elimina un producto del carrito
     */
    removeFromCart(productId) {
        delete this.cart[productId];
        this.updateCartUI();
        // Aquí deberías sincronizar con el servidor
    },
    
    /**
     * Actualiza la UI del carrito
     */
    updateCartUI() {
        // Actualizar contador
        const cartCount = Object.values(this.cart).reduce((sum, item) => sum + item.quantity, 0);
        const cartCountElements = document.querySelectorAll('[data-cart-count]');
        cartCountElements.forEach(el => el.textContent = cartCount);
        
        // Actualizar total
        const cartTotal = Object.values(this.cart).reduce((sum, item) => sum + (item.quantity * item.price), 0);
        const cartTotalElements = document.querySelectorAll('[data-cart-total]');
        cartTotalElements.forEach(el => el.textContent = cartTotal.toFixed(2));
    },
    
    /**
     * Obtiene el total del carrito
     */
    getTotal() {
        return Object.values(this.cart).reduce((sum, item) => sum + (item.quantity * item.price), 0);
    },
    
    /**
     * Obtiene la cantidad total de items
     */
    getItemCount() {
        return Object.values(this.cart).reduce((sum, item) => sum + item.quantity, 0);
    }
};

/**
 * Utilidades generales
 */
const Utils = {
    /**
     * Formatea moneda
     */
    formatCurrency(amount, currency = 'CUP') {
        return new Intl.NumberFormat('es-CU', {
            style: 'currency',
            currency: currency,
            minimumFractionDigits: 2
        }).format(amount);
    },
    
    /**
     * Copia texto al portapapeles
     */
    async copyToClipboard(text, button = null) {
        try {
            await navigator.clipboard.writeText(text);
            Notifications.success('Copiado al portapapeles');
            
            if (button) {
                const originalHTML = button.innerHTML;
                button.innerHTML = '<i class="fas fa-check"></i>';
                button.classList.add('bg-green-600');
                setTimeout(() => {
                    button.innerHTML = originalHTML;
                    button.classList.remove('bg-green-600');
                }, 2000);
            }
        } catch (error) {
            console.error('Error al copiar:', error);
            Notifications.error('Error al copiar al portapapeles');
        }
    },
    
    /**
     * Debounce para optimizar eventos
     */
    debounce(func, wait = APP_CONFIG.DEBOUNCE_DELAY) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },
    
    /**
     * Formatea fechas
     */
    formatDate(date, format = 'short') {
        const options = format === 'short' 
            ? { year: 'numeric', month: '2-digit', day: '2-digit' }
            : { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' };
            
        return new Date(date).toLocaleDateString('es-ES', options);
    }
};

/**
 * Inicialización cuando el DOM está listo
 */
document.addEventListener('DOMContentLoaded', function() {
    // Configurar CSRF
    CSRF.setupAjax();
    
    // Auto-ocultar mensajes flash
    const flashMessages = document.querySelectorAll('[data-flash-message]');
    flashMessages.forEach(message => {
        setTimeout(() => {
            message.style.opacity = '0';
            message.style.transform = 'translateY(-10px)';
            setTimeout(() => message.remove(), 300);
        }, 5000);
    });
    
    // Configurar preview de imágenes
    const imageInputs = document.querySelectorAll('input[type="file"][accept*="image"]');
    imageInputs.forEach(input => {
        const previewId = input.id + '-preview';
        const preview = document.getElementById(previewId);
        if (preview) {
            ProductManager.setupImagePreview(input, preview);
        }
    });
    
    // Configurar formularios AJAX
    const ajaxForms = document.querySelectorAll('[data-ajax-form]');
    ajaxForms.forEach(form => {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            await FormHandler.handleSubmit(form);
        });
    });
    
    // Configurar tooltips
    const tooltips = document.querySelectorAll('[data-tooltip]');
    tooltips.forEach(element => {
        element.addEventListener('mouseenter', function() {
            const tooltip = document.createElement('div');
            tooltip.className = 'absolute z-50 px-2 py-1 text-xs text-white bg-gray-800 rounded shadow-lg';
            tooltip.textContent = this.dataset.tooltip;
            document.body.appendChild(tooltip);
            
            const rect = this.getBoundingClientRect();
            tooltip.style.top = (rect.top - tooltip.offsetHeight - 5) + 'px';
            tooltip.style.left = (rect.left + rect.width/2 - tooltip.offsetWidth/2) + 'px';
            
            this.dataset.tooltipElement = tooltip;
        });
        
        element.addEventListener('mouseleave', function() {
            const tooltip = this.dataset.tooltipElement;
            if (tooltip) {
                document.body.removeChild(tooltip);
                delete this.dataset.tooltipElement;
            }
        });
    });
    
    // Configurar confirmación para acciones peligrosas
    const dangerousActions = document.querySelectorAll('[data-confirm]');
    dangerousActions.forEach(element => {
        element.addEventListener('click', function(e) {
            if (!confirm(this.dataset.confirm)) {
                e.preventDefault();
            }
        });
    });
    
    // Lazy loading de imágenes
    if ('IntersectionObserver' in window) {
        const lazyImages = document.querySelectorAll('img[data-lazy]');
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.lazy;
                    img.classList.add('fade-in');
                    imageObserver.unobserve(img);
                }
            });
        });
        
        lazyImages.forEach(img => imageObserver.observe(img));
    }
    
    // Manejar navegación con teclado
    document.addEventListener('keydown', function(e) {
        // Esc para cerrar modales
        if (e.key === 'Escape') {
            const modals = document.querySelectorAll('[data-modal]:not(.hidden)');
            modals.forEach(modal => modal.classList.add('hidden'));
        }
        
        // Ctrl+S para guardar formularios
        if (e.ctrlKey && e.key === 's') {
            e.preventDefault();
            const activeForm = document.querySelector('form:not([data-no-shortcut])');
            if (activeForm) {
                activeForm.dispatchEvent(new Event('submit', { cancelable: true }));
            }
        }
    });
});

/**
 * Funciones globales para uso en templates
 */
window.deleteProduct = ProductManager.deleteProduct.bind(ProductManager);
window.updateOrderStatus = OrderManager.updateStatus.bind(OrderManager);
window.copyToClipboard = Utils.copyToClipboard.bind(Utils);
window.showNotification = Notifications.show.bind(Notifications);

// Exportar para uso modular si es necesario
export {
    CSRF,
    Notifications,
    FormHandler,
    ProductManager,
    OrderManager,
    CartManager,
    Utils,
    APP_CONFIG
};
