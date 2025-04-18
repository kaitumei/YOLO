document.addEventListener('DOMContentLoaded', () => {
    const sidebar = document.querySelector('.sidebar');
    const sidebarToggle = document.querySelector('.sidebar-toggle');
    const sidebarOverlay = document.querySelector('.sidebar-overlay');
    const mobileNavTrigger = document.querySelector('.mobile-nav-trigger');
    let isDragging = false;
    let startX = 0;
    let touchStartTime = 0;

    // 响应式处理
    const handleResponsive = () => {
        const isMobile = window.innerWidth <= 768;
        
        // 移动端适配
        if (isMobile) {
            sidebar.classList.add('collapsed');
            mobileNavTrigger.style.display = 'flex';
        } else {
            // 桌面端恢复上次状态
            const savedState = localStorage.getItem('sidebarCollapsed') === 'true';
            sidebar.classList.toggle('collapsed', savedState);
            mobileNavTrigger.style.display = 'none';
        }
    };

    // 移动端触发器点击事件
    mobileNavTrigger.addEventListener('click', (e) => {
        e.stopPropagation();
        sidebar.classList.remove('collapsed');
    });

    // 点击遮罩层关闭侧边栏
    sidebarOverlay.addEventListener('click', () => {
        sidebar.classList.add('collapsed');
    });

    // 点击外部关闭侧边栏（移动端）
    document.addEventListener('click', (e) => {
        if (window.innerWidth > 768) return;
        
        if (!sidebar.contains(e.target) && 
            !sidebarToggle.contains(e.target) && 
            !mobileNavTrigger.contains(e.target)) {
            sidebar.classList.add('collapsed');
        }
    });

    // 添加移动端滑动手势
    sidebar.addEventListener('touchstart', (e) => {
        startX = e.touches[0].clientX;
        touchStartTime = Date.now();
        isDragging = true;
    }, { passive: true });

    sidebar.addEventListener('touchmove', (e) => {
        if (!isDragging) return;

        const currentX = e.touches[0].clientX;
        const diff = currentX - startX;
        
        // 左划关闭菜单
        if (diff < -50) {
            sidebar.classList.add('collapsed');
            isDragging = false;
        }
    }, { passive: true });
    
    // 监听touch结束
    sidebar.addEventListener('touchend', (e) => {
        const touchEndTime = Date.now();
        const touchDuration = touchEndTime - touchStartTime;
        
        // 快速滑动检测
        if (touchDuration < 250 && isDragging) {
            const endX = e.changedTouches[0].clientX;
            const diff = endX - startX;
            
            if (diff < -30) {
                sidebar.classList.add('collapsed');
            } else if (diff > 30) {
                sidebar.classList.remove('collapsed');
            }
        }
        
        isDragging = false;
    }, { passive: true });
    
    // 从屏幕左侧边缘滑动打开侧边栏
    document.addEventListener('touchstart', (e) => {
        if (window.innerWidth > 768) return;
        
        if (e.touches[0].clientX < 20) {
            startX = e.touches[0].clientX;
            isDragging = true;
            touchStartTime = Date.now();
        }
    }, { passive: true });
    
    document.addEventListener('touchmove', (e) => {
        if (!isDragging || window.innerWidth > 768) return;
        
        const currentX = e.touches[0].clientX;
        const diff = currentX - startX;
        
        if (diff > 50) {
            sidebar.classList.remove('collapsed');
            isDragging = false;
        }
    }, { passive: true });

    // 初始化
    handleResponsive();
    window.addEventListener('resize', handleResponsive);
    
    // 折叠/展开侧边栏
    sidebarToggle.addEventListener('click', (e) => {
        e.stopPropagation();
        sidebar.classList.toggle('collapsed');
        localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
    });

    // 移除活动菜单项的缩放动画效果
    const activeLinks = document.querySelectorAll('.sidebar-link.active');
    if (activeLinks.length > 0) {
        activeLinks.forEach(link => {
            // 防止active链接有缩放效果
            link.style.transform = 'none';
            link.style.transition = 'background-color 0.3s, color 0.3s, border-color 0.3s';
        });
    }

    // 自动关闭移动端侧边栏
    document.querySelectorAll('.sidebar-link').forEach(link => {
        link.addEventListener('click', (e) => {
            // 防止链接点击时的缩放效果
            link.style.transform = 'none';
            
            // 阻止默认动画效果
            e.preventDefault();
            const href = link.getAttribute('href');
            
            // 手动延迟导航以确保没有动画
            setTimeout(() => {
                if (href) window.location.href = href;
            }, 10);
            
            // 只在移动端自动关闭侧边栏
            if (window.innerWidth <= 768) {
                sidebar.classList.add('collapsed');
            }
        });
    });

    // 侧边栏透明度控制 - 初始化时就进行处理
    initOpacityControl();
});

// 初始化透明度控制函数
function initOpacityControl() {
    const sidebar = document.querySelector('.sidebar');
    
    // 直接设置不透明样式
    sidebar.style.background = '#ffffff';
    sidebar.style.backdropFilter = 'none';
    sidebar.style.webkitBackdropFilter = 'none';
    
    // 确保导航项背景也是不透明的
    const navItems = document.querySelectorAll('.sidebar-link');
    navItems.forEach(item => {
        item.style.backgroundColor = '#ffffff';
        item.style.opacity = '1';
        // 防止导航项有任何缩放效果
        item.style.transform = 'none';
    });
    
    // 更新CSS变量
    document.documentElement.style.setProperty('--glass-bg', 'rgba(255, 255, 255, 1)');
}

// 移除高亮动画缩放效果
function highlightNavItem(element) {
    // 防止有任何缩放效果
    element.style.transform = 'none';
    element.classList.add('highlight');
    setTimeout(() => {
        element.classList.remove('highlight');
    }, 1000);
}

// 获取当前激活的菜单项
const activeNavItem = document.querySelector('.sidebar-link.active');
if (activeNavItem) {
    // 立即应用transform:none避免缩放
    activeNavItem.style.transform = 'none';
    
    // 防止页面加载后的高亮动画
    // 如果需要高亮，取消下面的注释
    /*
    setTimeout(() => {
        highlightNavItem(activeNavItem);
    }, 500);
    */
}

// 全局透明度测试函数，可以在控制台直接调用
window.testSidebarOpacity = function(opacity) {
    const sidebar = document.querySelector('.sidebar');
    
    // 移除所有透明度类
    sidebar.classList.remove('opacity-medium', 'opacity-low');
    sidebar.classList.add('opacity-high');
    
    // 直接设置不透明样式
    sidebar.style.background = '#ffffff';
    sidebar.style.backdropFilter = 'none';
    sidebar.style.webkitBackdropFilter = 'none';
    
    // 确保导航项背景也是不透明的
    const navItems = document.querySelectorAll('.sidebar-link');
    navItems.forEach(item => {
        item.style.backgroundColor = '#ffffff';
        item.style.opacity = '1';
        // 防止有任何缩放效果
        item.style.transform = 'none';
    });
    
    // 更新CSS变量
    document.documentElement.style.setProperty('--glass-bg', 'rgba(255, 255, 255, 1)');
    
    return `侧边栏已设置为不透明`;
};

// 监听DOM加载
document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM已加载完成，准备应用透明度设置");
    setTimeout(() => {
        // 1秒后强制应用一次默认透明度，确保任何情况下都能正确应用
        const savedOpacity = localStorage.getItem('sidebarOpacity') || "95";
        window.testSidebarOpacity(savedOpacity);
        
        // 防止导航项缩放
        document.querySelectorAll('.sidebar-link').forEach(link => {
            link.style.transform = 'none';
        });
    }, 1000);
    
    // 添加刷新头像缓存的处理
    refreshAvatarCache();
});

// 刷新头像缓存的函数
function refreshAvatarCache() {
    // 获取所有头像图片元素
    const avatarImages = document.querySelectorAll('.header-avatar');
    
    // 为每个头像添加时间戳参数，强制刷新
    avatarImages.forEach(img => {
        const currentSrc = img.getAttribute('src');
        if (currentSrc && currentSrc.includes('/media/')) {
            // 检查是否已有时间戳参数
            const newSrc = currentSrc.includes('?') 
                ? `${currentSrc}&_t=${new Date().getTime()}` 
                : `${currentSrc}?_t=${new Date().getTime()}`;
                
            // 更新图片源
            img.setAttribute('src', newSrc);
        }
    });
    
    // 移除任何可能的错误处理器的副作用
    avatarImages.forEach(img => {
        // 先保存原始的错误处理函数
        const originalOnError = img.onerror;
        
        // 清空错误处理函数并重新设置
        img.onerror = null;
        img.onerror = originalOnError;
    });
}