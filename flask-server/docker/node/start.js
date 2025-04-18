/**
 * 服务器启动脚本 - 捕获并处理路由错误
 */

// 配置检查已添加
try {
  // 确保配置目录和文件存在
  console.log('开始检查配置目录和文件...');
  
  const fs = require('fs');
  const path = require('path');
  
  // 检查当前工作目录
  console.log('当前工作目录:', process.cwd());
  console.log('目录内容:', fs.readdirSync('.').join(', '));
  
  // 确保config目录存在
  if (!fs.existsSync('./config')) {
    console.log('config目录不存在，创建目录');
    fs.mkdirSync('./config', { recursive: true });
  }
  
  // 检查config目录内容
  if (fs.existsSync('./config')) {
    console.log('config目录内容:', fs.readdirSync('./config').join(', '));
  }
  
  // 检查db.js文件
  if (!fs.existsSync('./config/db.js')) {
    console.log('db.js文件不存在，尝试运行修复脚本');
    try {
      require('./fix-config');
    } catch (error) {
      console.error('运行修复脚本失败:', error.message);
      
      // 如果修复脚本失败，手动创建最小化的db.js
      console.log('创建简化版db.js文件');
      
      const minimalDbJs = `
module.exports = {
  query: async (sql, params = []) => {
    console.log('使用临时模拟查询函数');
    console.log('SQL:', sql);
    return [];
  },
  testConnection: async () => false,
  mockData: {
    notices: [],
    banners: []
  }
};`;
      
      fs.writeFileSync('./config/db.js', minimalDbJs);
      console.log('已创建简化版db.js文件');
    }
  }
  
  console.log('配置检查完成');
} catch (error) {
  console.error('配置检查失败:', error);
}

try {
  // 添加全局错误处理，特别是对path-to-regexp错误
  const originalRegExpExec = RegExp.prototype.exec;
  RegExp.prototype.exec = function(...args) {
    try {
      return originalRegExpExec.apply(this, args);
    } catch (error) {
      console.error('RegExp执行错误:', error);
      console.error('出错的RegExp模式:', this.source);
      return null; // 返回null而不是抛出错误
    }
  };

  // 在Express加载前修复已知的路由URL问题
  const path = require('path');
  const fs = require('fs');
  
  console.log('正在检查路由文件...');
  
  // 检查环境变量
  console.log('环境变量:', process.env.NODE_ENV);
  
  // 开始检查路由中的完整URL
  const findCompleteUrls = (dir) => {
    const files = fs.readdirSync(dir);
    files.forEach(file => {
      const filePath = path.join(dir, file);
      const stat = fs.statSync(filePath);
      
      if (stat.isDirectory()) {
        // 递归检查子目录
        findCompleteUrls(filePath);
      } else if (file.endsWith('.js')) {
        // 对JavaScript文件进行检查
        const content = fs.readFileSync(filePath, 'utf8');
        if (content.includes('https://git.new') || 
            /router\.(get|post|put|delete|use)\s*\(\s*["']https:\/\//.test(content) ||
            /app\.(get|post|put|delete|use)\s*\(\s*["']https:\/\//.test(content)) {
          console.error(`发现可能导致问题的路由文件: ${filePath}`);
          // 可以在这里自动修复问题
        }
      }
    });
  };
  
  // 检查routes目录
  findCompleteUrls(path.join(__dirname, 'routes'));
  
  // 启动主应用
  console.log('开始加载应用...');
  require('./app');
  console.log('应用已成功启动');
} catch (error) {
  console.error('启动服务器时发生致命错误:', error);
  
  // 如果是path-to-regexp错误，提供更多信息
  if (error.message && error.message.includes('Missing parameter name')) {
    console.error('这是一个路由定义错误，通常是由完整URL导致的。');
    console.error('请检查所有路由文件，确保没有使用完整URL (https://)作为路由路径。');
    console.error('应该使用相对路径，例如 "/" 或 "/api/resource" 而不是 "https://example.com/api/resource"');
    
    // 尝试从错误中提取问题URL
    const match = error.message.match(/at \d+: (.+)/);
    if (match && match[1]) {
      console.error('问题URL:', match[1]);
    }
  }
  
  process.exit(1);
} 