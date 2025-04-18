/**
 * 前台侧边栏增强脚本
 * 改善前台页面侧边栏的图标交互体验
 */

document.addEventListener('DOMContentLoaded', function() {
    // 侧边栏元素
    const sidebar = document.querySelector('.sidebar');
    if (!sidebar) return;
    
    // 不在CMS页面上运行
    if (document.body.classList.contains('cms-page')) return;
    
    // 记忆折叠状态
    const toggleBtn = document.querySelector('.sidebar-toggle');
    if (toggleBtn) {
        // 从本地存储读取上次的折叠状态
        const isSidebarCollapsed = localStorage.getItem('front_sidebar_collapsed') === 'true';
        
        // 应用上次的折叠状态
        if (!isSidebarCollapsed) {
            sidebar.classList.remove('collapsed');
            document.querySelector('.content').style.marginLeft = getComputedStyle(document.documentElement).getPropertyValue('--sidebar-width');
        }
        
        // 监听折叠/展开点击
        toggleBtn.addEventListener('click', function() {
            const isNowCollapsed = sidebar.classList.contains('collapsed');
            localStorage.setItem('front_sidebar_collapsed', !isNowCollapsed);
        });
    }
    
    // 所有导航链接
    const navLinks = document.querySelectorAll('.sidebar-link');
    
    // 为每个导航链接添加增强交互
    navLinks.forEach(link => {
        const icon = link.querySelector('svg');
        if (icon) {
            // 为图标添加悬停效果
            link.addEventListener('mouseenter', function() {
                icon.style.transition = 'transform 0.3s ease-out';
                icon.style.transform = 'scale(1.15)';
            });
            
            link.addEventListener('mouseleave', function() {
                icon.style.transition = 'transform 0.3s ease-out';
                icon.style.transform = '';
            });
            
            // 点击时的动画效果
            link.addEventListener('click', function() {
                // 只有当链接不是当前活动链接时才应用效果
                if (!link.classList.contains('active')) {
                    // 缩小-放大的弹性动画
                    icon.style.transition = 'transform 0.2s cubic-bezier(.17,.67,.38,1.46)';
                    icon.style.transform = 'scale(0.8)';
                    
                    setTimeout(() => {
                        icon.style.transform = 'scale(1.2)';
                        
                        setTimeout(() => {
                            icon.style.transform = '';
                        }, 150);
                    }, 100);
                }
            });
        }
        
        // 添加点击涟漪效果
        link.addEventListener('click', function(e) {
            if (this.classList.contains('active')) return;
            
            const rect = this.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            const ripple = document.createElement('span');
            ripple.classList.add('sidebar-ripple-effect');
            ripple.style.left = x + 'px';
            ripple.style.top = y + 'px';
            
            this.appendChild(ripple);
            
            setTimeout(() => {
                ripple.remove();
            }, 600);
        });
    });
    
    // 为折叠状态下的链接添加工具提示
    if (sidebar.classList.contains('collapsed')) {
        navLinks.forEach(link => {
            if (link.title) {
                link.addEventListener('mouseenter', function() {
                    const tooltip = document.createElement('div');
                    tooltip.classList.add('sidebar-tooltip');
                    tooltip.textContent = this.title;
                    tooltip.style.opacity = '0';
                    
                    document.body.appendChild(tooltip);
                    
                    const rect = this.getBoundingClientRect();
                    tooltip.style.top = rect.top + rect.height / 2 - tooltip.offsetHeight / 2 + 'px';
                    tooltip.style.left = rect.right + 10 + 'px';
                    
                    // 使用RAF确保元素已经渲染，然后应用动画
                    requestAnimationFrame(() => {
                        tooltip.style.opacity = '1';
                        tooltip.style.transform = 'translateX(0)';
                    });
                    
                    this.addEventListener('mouseleave', function() {
                        if (tooltip.parentNode) {
                            tooltip.style.opacity = '0';
                            tooltip.style.transform = 'translateX(-10px)';
                            
                            setTimeout(() => {
                                if (tooltip.parentNode) {
                                    tooltip.parentNode.removeChild(tooltip);
                                }
                            }, 200);
                        }
                    }, { once: true });
                });
            }
        });
    }
    
    // 添加CSS样式
    const style = document.createElement('style');
    style.textContent = `
        .sidebar-ripple-effect {
            position: absolute;
            border-radius: 50%;
            background: rgba(76, 175, 80, 0.3);
            transform: scale(0);
            animation: sidebar-ripple 0.6s ease-out;
            pointer-events: none;
            width: 100px;
            height: 100px;
            margin-top: -50px;
            margin-left: -50px;
        }
        
        @keyframes sidebar-ripple {
            to {
                transform: scale(2);
                opacity: 0;
            }
        }
        
        .sidebar-tooltip {
            position: fixed;
            background: rgba(51, 51, 51, 0.9);
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            pointer-events: none;
            z-index: 9999;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
            transition: opacity 0.2s ease, transform 0.2s ease;
            transform: translateX(-10px);
        }
        
        .sidebar-tooltip:after {
            content: '';
            position: absolute;
            left: -5px;
            top: 50%;
            transform: translateY(-50%);
            border-width: 5px 5px 5px 0;
            border-style: solid;
            border-color: transparent rgba(51, 51, 51, 0.9) transparent transparent;
        }
        
        /* 静态样式增强 */
        .sidebar-link svg {
            will-change: transform;
        }
    `;
    document.head.appendChild(style);
    
    // 增强导航组交互
    const navGroups = document.querySelectorAll('.nav-group');
    navGroups.forEach(group => {
        const title = group.querySelector('.nav-group-title');
        if (!title) return;
        
        // 为导航组标题添加悬停效果
        title.addEventListener('mouseenter', function() {
            this.style.color = '#4CAF50';
        });
        
        title.addEventListener('mouseleave', function() {
            this.style.color = '';
        });
    });
    
    // 用户头像增强
    const userAvatar = document.querySelector('.user-avatar');
    if (userAvatar) {
        const avatar = userAvatar.querySelector('.header-avatar');
        if (avatar) {
            // 添加鼠标悬停时的光晕效果
            userAvatar.addEventListener('mouseenter', function() {
                avatar.style.boxShadow = '0 0 0 2px rgba(76, 175, 80, 0.6), 0 2px 8px rgba(0, 0, 0, 0.2)';
            });
            
            userAvatar.addEventListener('mouseleave', function() {
                avatar.style.boxShadow = '';
            });
        }
    }
    
    // 退出按钮效果增强
    const logoutBtn = document.querySelector('.logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('mouseenter', function() {
            const svg = this.querySelector('svg');
            if (svg) {
                svg.style.fill = '#e53935';
                svg.style.transform = 'rotate(-12deg)';
            }
        });
        
        logoutBtn.addEventListener('mouseleave', function() {
            const svg = this.querySelector('svg');
            if (svg) {
                svg.style.fill = '';
                svg.style.transform = '';
            }
        });
    }
}); 