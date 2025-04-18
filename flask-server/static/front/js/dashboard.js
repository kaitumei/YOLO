// dashboard.js

// 页面加载完成后执行
// document.addEventListener('DOMContentLoaded', function() {
//     // 示例1：显示欢迎消息
//     const welcomeMessage = document.getElementById('welcome-message');
//     if (welcomeMessage) {
//         welcomeMessage.textContent = '欢迎使用慧眼通途平台！';
//     }
//
//     // 示例2：更新当前时间
//     const currentTimeElement = document.getElementById('current-time');
//     if (currentTimeElement) {
//         updateTime();
//         // 每秒更新一次时间
//         setInterval(updateTime, 1000);
//     }
//
//     // 示例3：获取视频检测数据
//     fetchVideoDetectionData();
//
//     // 示例4：事件监听示例
//     const loginButton = document.getElementById('login-button');
//     if (loginButton) {
//         loginButton.addEventListener('click', function() {
//             alert('登录按钮被点击！');
//         });
//     }
// });
//
// // 更新时间函数
// function updateTime() {
//     const now = new Date();
//     const formattedTime = now.toLocaleString();
//     const currentTimeElement = document.getElementById('current-time');
//     if (currentTimeElement) {
//         currentTimeElement.textContent = formattedTime;
//     }
// }
//
// // 获取视频检测数据
// async function fetchVideoDetectionData() {
//     try {
//         const response = await fetch('/check/video');
//         if (!response.ok) {
//             throw new Error('网络响应不正常');
//         }
//         const data = await response.json();
//         console.log('视频检测数据:', data);
//
//         // 在页面上显示数据
//         displayDetectionData(data);
//     } catch (error) {
//         console.error('获取视频检测数据失败:', error);
//         alert('获取视频检测数据失败，请检查网络连接或稍后再试。');
//     }
// }
//
// // 显示视频检测数据
// function displayDetectionData(data) {
//     const detectionResultsContainer = document.getElementById('detection-results');
//     if (!detectionResultsContainer) {
//         return;
//     }
//
//     let html = '<table><thead><tr><th>类别</th><th>置信度</th><th>坐标</th></tr></thead><tbody>';
//     if (data && data.length > 0) {
//         data.forEach(item => {
//             html += `<tr>
//                         <td>${item.category}</td>
//                         <td>${item.confidence}</td>
//                         <td>${item.coordinates}</td>
//                      </tr>`;
//         });
//     } else {
//         html += '<tr><td colspan="3">暂无检测数据</td></tr>';
//     }
//     html += '</tbody></table>';
//
//     detectionResultsContainer.innerHTML = html;
// }