// ============================================================
// ADMIN PANEL - COMPLETE JAVASCRIPT
// All JavaScript in one file for better performance
// ============================================================

(function() {
    'use strict';

    // ===== DOM Ready =====
    document.addEventListener('DOMContentLoaded', function() {

        // ============================================================
        // SIDEBAR TOGGLE (Mobile)
        // ============================================================
        const sidebar = document.getElementById('sidebar');
        const overlay = document.getElementById('sidebarOverlay');
        const hamburger = document.getElementById('hamburgerBtn');

        function toggleSidebar() {
            sidebar.classList.toggle('open');
            overlay.classList.toggle('active');
            document.body.style.overflow = sidebar.classList.contains('open') ? 'hidden' : '';
        }

        if (hamburger) {
            hamburger.addEventListener('click', function(e) {
                e.stopPropagation();
                toggleSidebar();
            });
        }

        if (overlay) {
            overlay.addEventListener('click', toggleSidebar);
        }

        // Close sidebar on link click (mobile)
        document.querySelectorAll('.sidebar .nav-link').forEach(function(link) {
            link.addEventListener('click', function() {
                if (window.innerWidth <= 992) {
                    setTimeout(function() {
                        if (sidebar.classList.contains('open')) toggleSidebar();
                    }, 200);
                }
            });
        });

        // Close sidebar on resize
        window.addEventListener('resize', function() {
            if (window.innerWidth > 992 && sidebar.classList.contains('open')) {
                toggleSidebar();
            }
        });

        // ============================================================
        // PANELS PAGE FUNCTIONS
        // ============================================================
        if (document.getElementById('panelsTableBody')) {
            let panelsData = [];
            let selectedInbounds = [];
            let modalInstance = null;

            // ===== Toast =====
            function showToast(message, type) {
                type = type || 'success';
                var container = document.getElementById('toastContainer');
                if (!container) return;
                var icons = { success: '✅', error: '❌', warning: '⚠️' };
                var toast = document.createElement('div');
                toast.className = 'toast-msg ' + type;
                toast.innerHTML = '<span>' + (icons[type] || '📌') + '</span> <span>' + message + '</span>';
                container.appendChild(toast);
                setTimeout(function() {
                    toast.style.opacity = '0';
                    toast.style.transform = 'translateX(100%)';
                    toast.style.transition = 'all 0.3s ease';
                    setTimeout(function() { toast.remove(); }, 350);
                }, 3500);
            }

            // ===== Spinner =====
            function showSpinner(show) {
                var overlay = document.getElementById('spinnerOverlay');
                if (!overlay) return;
                overlay.classList.toggle('active', show);
            }

            // ===== Load Panels =====
            function loadPanels() {
                showSpinner(true);
                fetch('/admin/api/panels')
                    .then(function(r) { return r.json(); })
                    .then(function(result) {
                        if (result.status === 'success') {
                            panelsData = result.data || [];
                            renderPanelsTable();
                        } else {
                            showToast('خطا در بارگذاری پنل‌ها', 'error');
                        }
                    })
                    .catch(function() { showToast('خطا در اتصال به سرور', 'error'); })
                    .finally(function() { showSpinner(false); });
            }

            // ===== Render Table =====
            function renderPanelsTable() {
                var tbody = document.getElementById('panelsTableBody');
                if (!tbody) return;

                if (!panelsData || panelsData.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="8"><div class="empty-state"><span class="icon">🖥️</span><h5>هیچ پنلی ثبت نشده است</h5><p>با کلیک روی دکمه "افزودن پنل" اولین پنل خود را اضافه کنید</p></div></td></tr>';
                    return;
                }

                var html = '';
                panelsData.forEach(function(panel, index) {
                    var statusClass = getStatusClass(panel.status);
                    var statusText = getStatusText(panel.status);
                    var inboundTags = (panel.inbound_ids || []).map(function(id) {
                        return '<span class="badge-pastel blue">📡 ' + id + '</span>';
                    }).join(' ') || '<span style="color:rgba(255,255,255,0.2);font-size:0.7rem;">—</span>';

                    html += '<tr>' +
                        '<td style="color:rgba(255,255,255,0.3);font-size:0.75rem;">' + (index + 1) + '</td>' +
                        '<td class="name">' + panel.name + '</td>' +
                        '<td><span class="url" title="' + panel.url + '">' + panel.url + '</span></td>' +
                        '<td>' + inboundTags + '</td>' +
                        '<td><span class="badge-status ' + statusClass + '">' + statusText + '</span></td>' +
                        '<td><span style="color:#fff;">' + (panel.users_count || 0) + '</span></td>' +
                        '<td style="font-size:0.65rem;color:rgba(255,255,255,0.3);">' + (panel.last_check ? new Date(panel.last_check).toLocaleString('fa-IR') : '—') + '</td>' +
                        '<td><div class="d-flex gap-1">' +
                        '<button class="btn-sm btn-sm-check" onclick="checkPanel(' + panel.id + ')"><i class="bi bi-arrow-repeat"></i></button>' +
                        '<button class="btn-sm btn-sm-edit" onclick="editPanel(' + panel.id + ')"><i class="bi bi-pencil"></i></button>' +
                        '<button class="btn-sm btn-sm-delete" onclick="deletePanel(' + panel.id + ')"><i class="bi bi-trash"></i></button>' +
                        '</div></td></tr>';
                });
                tbody.innerHTML = html;
            }

            // ===== Status Helpers =====
            function getStatusClass(status) {
                var map = { 'healthy': 'healthy', 'warning': 'warning', 'offline': 'offline', 'unknown': 'unknown' };
                return map[status] || 'unknown';
            }
            function getStatusText(status) {
                var map = { 'healthy': '✅ سالم', 'warning': '⚠️ هشدار', 'offline': '❌ قطع', 'unknown': '⏳ نامشخص' };
                return map[status] || '⏳ نامشخص';
            }

            // ===== Modal =====
            function getModal() {
                if (!modalInstance) {
                    var el = document.getElementById('panelModal');
                    if (!el) return null;
                    modalInstance = new bootstrap.Modal(el, { backdrop: 'static', keyboard: true });
                }
                return modalInstance;
            }

            // ===== Open Add Modal =====
            window.openAddModal = function() {
                document.getElementById('panelModalTitle').textContent = '➕ افزودن پنل جدید';
                document.getElementById('panelId').value = '';
                document.getElementById('panelName').value = '';
                document.getElementById('panelUrl').value = '';
                document.getElementById('panelToken').value = '';
                document.getElementById('inboundContainer').innerHTML = '<small class="text-muted">برای انتخاب Inbound، دکمه "بررسی Inbound‌ها" را بزنید</small>';
                document.getElementById('panelStatusDisplay').innerHTML = '<span class="badge-status unknown">⏳ بررسی نشده</span>';
                document.getElementById('panelUsersDisplay').innerHTML = '<span style="color:rgba(255,255,255,0.4);">-</span>';
                selectedInbounds = [];
                var modal = getModal();
                if (modal) modal.show();
            };

            // ===== Edit Panel =====
            window.editPanel = function(id) {
                showSpinner(true);
                fetch('/admin/api/panels')
                    .then(function(r) { return r.json(); })
                    .then(function(result) {
                        if (result.status === 'success') {
                            var panel = result.data.find(function(p) { return p.id === id; });
                            if (!panel) { showToast('پنل پیدا نشد', 'error'); return; }
                            document.getElementById('panelModalTitle').textContent = '✏️ ویرایش پنل';
                            document.getElementById('panelId').value = panel.id;
                            document.getElementById('panelName').value = panel.name;
                            document.getElementById('panelUrl').value = panel.url;
                            document.getElementById('panelToken').value = panel.api_token || '';
                            if (panel.inbound_ids && panel.inbound_ids.length > 0) {
                                selectedInbounds = panel.inbound_ids;
                                renderInboundSelection(panel.inbound_ids);
                            }
                            var sc = getStatusClass(panel.status);
                            var st = getStatusText(panel.status);
                            document.getElementById('panelStatusDisplay').innerHTML = '<span class="badge-status ' + sc + '">' + st + '</span>';
                            document.getElementById('panelUsersDisplay').innerHTML = '<span style="color:#fff;">' + (panel.users_count || 0) + '</span>';
                            var modal = getModal();
                            if (modal) modal.show();
                        }
                    })
                    .catch(function() { showToast('خطا در بارگذاری', 'error'); })
                    .finally(function() { showSpinner(false); });
            };

            // ===== Delete Panel =====
            window.deletePanel = function(id) {
                if (!confirm('آیا از حذف این پنل اطمینان دارید؟')) return;
                showSpinner(true);
                fetch('/admin/api/panels/' + id, { method: 'DELETE' })
                    .then(function(r) { return r.json(); })
                    .then(function(result) {
                        if (result.status === 'success') { showToast('پنل حذف شد', 'success'); loadPanels(); }
                        else { showToast(result.message || 'خطا در حذف', 'error'); }
                    })
                    .catch(function() { showToast('خطا در ارتباط با سرور', 'error'); })
                    .finally(function() { showSpinner(false); });
            };

            // ===== Check Panel Status =====
            window.checkPanel = function(id) {
                showSpinner(true);
                fetch('/admin/api/panels/' + id + '/check-status', { method: 'POST' })
                    .then(function(r) { return r.json(); })
                    .then(function(result) {
                        if (result.status === 'success') { showToast('وضعیت بررسی شد', 'success'); loadPanels(); }
                        else { showToast(result.message || 'خطا در بررسی', 'error'); }
                    })
                    .catch(function() { showToast('خطا در ارتباط با سرور', 'error'); })
                    .finally(function() { showSpinner(false); });
            };

            // ===== Fetch Inbounds =====
            window.fetchInbounds = function() {
                var url = document.getElementById('panelUrl').value.trim();
                var token = document.getElementById('panelToken').value.trim();
                if (!url || !token) { showToast('لطفاً URL و توکن را وارد کنید', 'warning'); return; }
                showSpinner(true);
                fetch('/admin/api/panels/fetch-inbounds', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url, api_token: token })
                })
                    .then(function(r) { return r.json(); })
                    .then(function(result) {
                        if (result.status === 'success') {
                            var inbounds = result.data.inbounds || [];
                            renderInboundSelection(inbounds);
                            var sc = getStatusClass(result.data.panel_status || 'healthy');
                            var st = getStatusText(result.data.panel_status || 'healthy');
                            document.getElementById('panelStatusDisplay').innerHTML = '<span class="badge-status ' + sc + '">' + st + '</span>';
                            document.getElementById('panelUsersDisplay').innerHTML = '<span style="color:#fff;">' + (result.data.users_count || 0) + '</span>';
                            showToast('✅ ' + inbounds.length + ' Inbound پیدا شد', 'success');
                        } else {
                            showToast(result.message || 'خطا در دریافت Inbound‌ها', 'error');
                        }
                    })
                    .catch(function() { showToast('خطا در ارتباط با سرور', 'error'); })
                    .finally(function() { showSpinner(false); });
            };

            // ===== Render Inbound Selection =====
            function renderInboundSelection(inbounds) {
                var container = document.getElementById('inboundContainer');
                if (!container) return;
                if (!inbounds || inbounds.length === 0) {
                    container.innerHTML = '<small class="text-muted">هیچ Inboundی پیدا نشد</small>';
                    return;
                }
                var html = '';
                inbounds.forEach(function(id) {
                    var checked = selectedInbounds.indexOf(String(id)) >= 0 ? 'checked' : '';
                    var selectedClass = selectedInbounds.indexOf(String(id)) >= 0 ? 'selected' : '';
                    html += '<label class="inbound-item ' + selectedClass + '">' +
                        '<input type="checkbox" value="' + id + '" ' + checked + ' onchange="toggleInbound(this)">' +
                        '📡 ' + id +
                        '</label>';
                });
                container.innerHTML = html;
            }

            // ===== Toggle Inbound =====
            window.toggleInbound = function(cb) {
                var value = cb.value;
                var parent = cb.closest('.inbound-item');
                if (cb.checked) {
                    if (selectedInbounds.indexOf(value) < 0) selectedInbounds.push(value);
                    if (parent) parent.classList.add('selected');
                } else {
                    selectedInbounds = selectedInbounds.filter(function(id) { return id !== value; });
                    if (parent) parent.classList.remove('selected');
                }
            };

            // ===== Save Panel =====
            window.savePanel = function() {
                var id = document.getElementById('panelId').value;
                var name = document.getElementById('panelName').value.trim();
                var url = document.getElementById('panelUrl').value.trim();
                var token = document.getElementById('panelToken').value.trim();

                if (!name) { showToast('لطفاً نام پنل را وارد کنید', 'error'); return; }
                if (!url) { showToast('لطفاً آدرس URL را وارد کنید', 'error'); return; }
                if (!token) { showToast('لطفاً توکن API را وارد کنید', 'error'); return; }

                var data = { name: name, url: url, api_token: token, inbound_ids: selectedInbounds, is_active: true };
                var method = id ? 'PUT' : 'POST';
                var endpoint = id ? '/admin/api/panels/' + id : '/admin/api/panels';

                showSpinner(true);
                fetch(endpoint, {
                    method: method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                })
                    .then(function(r) { return r.json(); })
                    .then(function(result) {
                        if (result.status === 'success') {
                            showToast(result.message || 'پنل ذخیره شد', 'success');
                            var modal = getModal();
                            if (modal) modal.hide();
                            setTimeout(loadPanels, 300);
                        } else {
                            showToast(result.message || 'خطا در ذخیره', 'error');
                        }
                    })
                    .catch(function() { showToast('خطا در ارتباط با سرور', 'error'); })
                    .finally(function() { showSpinner(false); });
            };

            // ===== Reset Modal =====
            function resetModal() {
                document.getElementById('panelId').value = '';
                document.getElementById('panelName').value = '';
                document.getElementById('panelUrl').value = '';
                document.getElementById('panelToken').value = '';
                document.getElementById('inboundContainer').innerHTML = '<small class="text-muted">برای انتخاب Inbound، دکمه "بررسی Inbound‌ها" را بزنید</small>';
                document.getElementById('panelStatusDisplay').innerHTML = '<span class="badge-status unknown">⏳ بررسی نشده</span>';
                document.getElementById('panelUsersDisplay').innerHTML = '<span style="color:rgba(255,255,255,0.4);">-</span>';
                selectedInbounds = [];
            }

            // ===== Modal Events =====
            var modalEl = document.getElementById('panelModal');
            if (modalEl) {
                modalEl.addEventListener('hidden.bs.modal', resetModal);
                document.getElementById('modalCloseBtn').addEventListener('click', function() { var m = getModal(); if (m) m.hide(); });
                document.getElementById('modalCancelBtn').addEventListener('click', function() { var m = getModal(); if (m) m.hide(); });
                document.getElementById('modalSaveBtn').addEventListener('click', window.savePanel);
            }

            // ===== Load Panels =====
            loadPanels();
        }

    });

})();
