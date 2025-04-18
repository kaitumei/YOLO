/**
 * CMS侧边栏增强脚本
 * 改善后台管理系统侧边栏的用户体验
 */

document.addEventListener('DOMContentLoaded', function() {
    // 确保在CMS页面上运行
    if (!document.body.classList.contains('cms-page')) return;
    
    // 侧边栏折叠状态管理
    const sidebar = document.querySelector('.sidebar');
    const toggleBtn = document.querySelector('.sidebar-toggle');
    
    // 从localStorage读取上次的折叠状态
    const isSidebarCollapsed = localStorage.getItem('cms_sidebar_collapsed') === 'true';
    
    // 应用上次的折叠状态
    if (!isSidebarCollapsed) {
        sidebar.classList.remove('collapsed');
        document.querySelector('.content').style.marginLeft = getComputedStyle(document.documentElement).getPropertyValue('--sidebar-width');
    }
    
    // 监听侧边栏折叠/展开事件
    if (toggleBtn) {
        toggleBtn.addEventListener('click', function() {
            const isNowCollapsed = sidebar.classList.contains('collapsed');
            localStorage.setItem('cms_sidebar_collapsed', !isNowCollapsed);
        });
    }
    
    // 增强导航链接的交互体验
    const navLinks = document.querySelectorAll('.sidebar-link');
    navLinks.forEach(link => {
        // 添加涟漪效果
        link.addEventListener('click', function(e) {
            const rect = this.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            const ripple = document.createElement('span');
            ripple.classList.add('nav-ripple-effect');
            ripple.style.left = x + 'px';
            ripple.style.top = y + 'px';
            
            this.appendChild(ripple);
            
            setTimeout(() => {
                ripple.remove();
            }, 600);
        });
        
        // 增强图标交互
        const icon = link.querySelector('svg');
        if (icon) {
            // 鼠标悬停时图标微动效
            link.addEventListener('mouseenter', function() {
                icon.style.transition = 'transform 0.3s ease-out';
                icon.style.transform = 'scale(1.15) translateY(-2px)';
            });
            
            link.addEventListener('mouseleave', function() {
                icon.style.transition = 'transform 0.3s ease-out';
                icon.style.transform = '';
            });
            
            // 点击时的弹跳效果
            link.addEventListener('click', function() {
                icon.style.transition = 'transform 0.2s cubic-bezier(.17,.67,.38,1.46)';
                icon.style.transform = 'scale(0.8)';
                
                setTimeout(() => {
                    icon.style.transform = 'scale(1.2)';
                    
                    setTimeout(() => {
                        icon.style.transform = '';
                    }, 150);
                }, 100);
            });
        }
        
        // 添加工具提示
        if (link.title && sidebar.classList.contains('collapsed')) {
            link.addEventListener('mouseenter', function(e) {
                const tooltip = document.createElement('div');
                tooltip.classList.add('nav-tooltip');
                tooltip.textContent = this.title;
                
                document.body.appendChild(tooltip);
                
                const rect = this.getBoundingClientRect();
                tooltip.style.top = rect.top + rect.height / 2 - tooltip.offsetHeight / 2 + 'px';
                tooltip.style.left = rect.right + 10 + 'px';
                
                this.dataset.tooltip = true;
                
                this.addEventListener('mouseleave', function() {
                    if (tooltip.parentNode) {
                        tooltip.parentNode.removeChild(tooltip);
                    }
                    delete this.dataset.tooltip;
                }, { once: true });
            });
        }
    });
    
    // 添加CSS样式
    const style = document.createElement('style');
    style.textContent = `
        .nav-ripple-effect {
            position: absolute;
            border-radius: 50%;
            background: rgba(76, 175, 80, 0.4);
            transform: scale(0);
            animation: ripple-animation 0.6s ease-out;
            pointer-events: none;
            width: 100px;
            height: 100px;
            margin-top: -50px;
            margin-left: -50px;
        }
        
        @keyframes ripple-animation {
            to {
                transform: scale(2);
                opacity: 0;
            }
        }
        
        .nav-tooltip {
            position: fixed;
            background: rgba(51, 51, 51, 0.9);
            color: white;
            padding: 5px 10px;
            border-radius: 4px;
            font-size: 12px;
            pointer-events: none;
            z-index: 9999;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
            animation: tooltip-appear 0.2s ease-out;
        }
        
        @keyframes tooltip-appear {
            from {
                opacity: 0;
                transform: translateX(-5px);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }
        
        .nav-tooltip:after {
            content: '';
            position: absolute;
            left: -5px;
            top: 50%;
            transform: translateY(-50%);
            border-width: 5px 5px 5px 0;
            border-style: solid;
            border-color: transparent rgba(51, 51, 51, 0.9) transparent transparent;
        }
        
        /* 图标增强样式 */
        .sidebar-link svg {
            will-change: transform;
        }
        
        .sidebar-link.active svg {
            transform: scale(1.05);
        }
    `;
    document.head.appendChild(style);
    
    // 让菜单组可折叠
    const navGroups = document.querySelectorAll('.nav-group');
    navGroups.forEach(group => {
        const title = group.querySelector('.nav-group-title');
        const links = Array.from(group.querySelectorAll('.sidebar-link'));
        
        if (title && links.length > 0) {
            title.style.cursor = 'pointer';
            
            // 检查是否有本组内的活动链接
            const hasActiveLink = links.some(link => link.classList.contains('active'));
            
            // 从localStorage获取组的折叠状态
            const groupId = title.textContent.trim().toLowerCase().replace(/\s+/g, '_');
            const isGroupCollapsed = localStorage.getItem(`cms_group_${groupId}_collapsed`) === 'true';
            
            // 如果应该折叠并且没有活动链接，则折叠
            if (isGroupCollapsed && !hasActiveLink) {
                links.forEach(link => {
                    link.style.display = 'none';
                });
                title.classList.add('collapsed');
            }
            
            title.addEventListener('click', function() {
                const isNowCollapsed = this.classList.contains('collapsed');
                
                if (isNowCollapsed) {
                    // 展开
                    links.forEach(link => {
                        link.style.display = '';
                    });
                    this.classList.remove('collapsed');
                    localStorage.setItem(`cms_group_${groupId}_collapsed`, 'false');
                } else {
                    // 折叠
                    links.forEach(link => {
                        link.style.display = 'none';
                    });
                    this.classList.add('collapsed');
                    localStorage.setItem(`cms_group_${groupId}_collapsed`, 'true');
                }
            });
        }
    });
}); 