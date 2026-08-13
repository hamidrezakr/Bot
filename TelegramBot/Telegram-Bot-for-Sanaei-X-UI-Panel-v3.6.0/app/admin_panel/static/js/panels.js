/**
 * Panels Management Module
 * Handles CRUD operations for X-UI panels
 */

const PanelsModule = {
    // ============ State ============
    panels: [],
    
    // ============ Init ============
    init: function() {
        this.loadPanels();
        this.bindEvents();
    },
    
    // ============ Load Panels ============
    loadPanels: function() {
        $.get('/admin/api/panels', (data) => {
            this.panels = data;
            this.renderTable(data);
        }).fail(() => {
            showToast('خطا در بارگذاری پنل‌ها', 'error');
        });
    },
    
    // ============ Render Table ============
    renderTable: function(panels) {
        const tbody = $('#panelsTableBody');
        tbody.empty();
        
        if (panels.length === 0) {
            tbody.html('<tr><td colspan="6" class="text-center">هیچ پنلی ثبت نشده است</td></tr>');
            return;
        }
        
        panels.forEach((panel, index) => {
            const row = `
                <tr>
                    <td>${index + 1}</td>
                    <td><strong>${panel.name}</strong></td>
                    <td><a href="${panel.url}" target="_blank">${panel.url}</a></td>
                    <td><span class="badge badge-${panel.status === 'active' ? 'active' : 'inactive'}">${panel.status === 'active' ? 'فعال' : 'غیرفعال'}</span></td>
                    <td>${panel.user_count || 0}</td>
                    <td>
                        <button class="btn btn-sm btn-warning" onclick="PanelsModule.editPanel(${panel.id})">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="PanelsModule.deletePanel(${panel.id})">
                            <i class="fas fa-trash"></i>
                        </button>
                        <button class="btn btn-sm btn-info" onclick="PanelsModule.testPanel(${panel.id})">
                            <i class="fas fa-plug"></i>
                        </button>
                    </td>
                </tr>
            `;
            tbody.append(row);
        });
    },
    
    // ============ Add Panel ============
    addPanel: function(data) {
        $.post('/admin/api/panels', data, (response) => {
            if (response.success) {
                showToast('پنل با موفقیت اضافه شد', 'success');
                this.loadPanels();
                $('#addPanelForm')[0].reset();
            } else {
                showToast(response.message || 'خطا در افزودن پنل', 'error');
            }
        }).fail(() => {
            showToast('خطا در ارتباط با سرور', 'error');
        });
    },
    
    // ============ Delete Panel ============
    deletePanel: function(id) {
        if (!confirm('آیا از حذف این پنل مطمئن هستید؟')) return;
        
        $.ajax({
            url: `/admin/api/panels/${id}`,
            method: 'DELETE',
            success: (response) => {
                if (response.success) {
                    showToast('پنل با موفقیت حذف شد', 'success');
                    this.loadPanels();
                } else {
                    showToast(response.message || 'خطا در حذف پنل', 'error');
                }
            },
            error: () => {
                showToast('خطا در ارتباط با سرور', 'error');
            }
        });
    },
    
    // ============ Test Panel ============
    testPanel: function(id) {
        $.post(`/admin/api/panels/${id}/test`, (response) => {
            if (response.success) {
                showToast('✅ اتصال به پنل موفق بود', 'success');
            } else {
                showToast('❌ اتصال به پنل ناموفق بود', 'error');
            }
        });
    },
    
    // ============ Bind Events ============
    bindEvents: function() {
        $('#addPanelForm').on('submit', (e) => {
            e.preventDefault();
            const data = {
                name: $('#panelName').val(),
                url: $('#panelUrl').val(),
                token: $('#panelToken').val()
            };
            this.addPanel(data);
        });
    }
};

// ============ Toast Helper ============
function showToast(message, type = 'info') {
    const colors = {
        success: '#2ecc71',
        error: '#e74c3c',
        info: '#3498db',
        warning: '#f39c12'
    };
    
    const toast = $(`
        <div class="toast-notification" style="
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: ${colors[type] || colors.info};
            color: #fff;
            padding: 15px 30px;
            border-radius: 8px;
            box-shadow: 0 5px 30px rgba(0,0,0,0.2);
            z-index: 9999;
            font-weight: 500;
            direction: rtl;
        ">
            ${message}
        </div>
    `);
    
    $('body').append(toast);
    
    setTimeout(() => {
        toast.fadeOut(500, function() {
            $(this).remove();
        });
    }, 3000);
}

// ============ Init on DOM Ready ============
$(document).ready(() => {
    PanelsModule.init();
});