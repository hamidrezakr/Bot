
/**
 * Settings Module
 * Manages bot settings like welcome message, help text, etc.
 */

const SettingsModule = {
    // ============ Init ============
    init: function() {
        this.loadSettings();
        this.bindEvents();
    },
    
    // ============ Load Settings ============
    loadSettings: function() {
        $.get('/admin/api/settings', (data) => {
            $('#welcomeMessage').val(data.welcome_message || '');
            $('#helpMessage').val(data.help_message || '');
            $('#botStatus').val(data.bot_status || 'active');
        }).fail(() => {
            showToast('خطا در بارگذاری تنظیمات', 'error');
        });
    },
    
    // ============ Save Settings ============
    saveSettings: function(data) {
        $.ajax({
            url: '/admin/api/settings',
            method: 'PUT',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: (response) => {
                if (response.success) {
                    showToast('تنظیمات با موفقیت ذخیره شد', 'success');
                } else {
                    showToast(response.message || 'خطا در ذخیره تنظیمات', 'error');
                }
            },
            error: () => {
                showToast('خطا در ارتباط با سرور', 'error');
            }
        });
    },
    
    // ============ Bind Events ============
    bindEvents: function() {
        $('#settingsForm').on('submit', (e) => {
            e.preventDefault();
            
            const data = {
                welcome_message: $('#welcomeMessage').val(),
                help_message: $('#helpMessage').val(),
                bot_status: $('#botStatus').val()
            };
            
            this.saveSettings(data);
        });
    }
};

// ============ Init on DOM Ready ============
$(document).ready(() => {
    SettingsModule.init();
});