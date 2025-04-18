        // const YOLO_SERVER = 'http://192.168.111.148:5000';  // 替换为实际IP
        // let isPaused = false;
        //
        // // 视频上传处理
        // document.getElementById('uploadForm').addEventListener('submit', async (e) => {
        //     e.preventDefault();
        //     const formData = new FormData();
        //     formData.append('video', e.target.video.files[0]);
        //
        //     // 清空现有显示
        //     document.getElementById('results').innerHTML = '';
        //     document.getElementById('liveFeed').src = '';
        //
        //     // 提交到YOLO服务
        //     try {
        //         const response = await fetch(`${YOLO_SERVER}/api/upload`, {
        //             method: 'POST',
        //             body: formData
        //         });
        //         if (response.ok) {
        //             // 启动视频流显示
        //             document.getElementById('liveFeed').src = `${YOLO_SERVER}/api/stream`;
        //             startResultUpdates();
        //         }
        //     } catch (error) {
        //         console.error('上传失败:', error);
        //     }
        // });
        //
        // // 定期更新检测结果
        // function startResultUpdates() {
        //     setInterval(async () => {
        //         try {
        //             const response = await fetch(`${YOLO_SERVER}/api/results`);
        //             const data = await response.json();
        //             const tbody = document.getElementById('results');
        //             tbody.innerHTML = data.map(item => `
        //                 <tr>
        //                     <td>${item.class}</td>
        //                     <td>${item.confidence}</td>
        //                     <td>${item.coordinates.join(', ')}</td>
        //                 </tr>
        //             `).join('');
        //         } catch (error) {
        //             console.error('获取结果失败:', error);
        //         }
        //     }, 1000);
        // }
        //
        // // 暂停/恢复控制
        // async function togglePause() {
        //     isPaused = !isPaused;
        //     const endpoint = isPaused ? '/api/pause' : '/api/resume';
        //     try {
        //         await fetch(`${YOLO_SERVER}${endpoint}`, { method: 'POST' });
        //         document.getElementById('pauseBtn').textContent =
        //             isPaused ? '恢复检测' : '暂停检测';
        //     } catch (error) {
        //         console.error('控制请求失败:', error);
        //     }
        // }


        // YOLO服务地址
const YOLO_SERVER = 'http://192.168.111.148:5000';  // 替换为实际IP
let isPaused = false;

// 视频预览功能
document.getElementById('videoInput').addEventListener('change', function(e) {
    const videoPreview = document.getElementById('previewVideo');
    const file = e.target.files[0];
    if (file) {
        const objectURL = URL.createObjectURL(file);
        videoPreview.src = objectURL;
        videoPreview.style.display = 'block';
        document.querySelector('.preview-tip').style.display = 'none';
    } else {
        videoPreview.src = '';
        videoPreview.style.display = 'none';
        document.querySelector('.preview-tip').style.display = 'block';
    }
});

// 视频上传处理
document.getElementById('uploadForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData();
    formData.append('video', e.target.video.files[0]);

    // 显示加载动画
    const loadingSpinner = document.getElementById('loadingSpinner');
    loadingSpinner.style.display = 'block';

    // 清空现有显示
    document.getElementById('results').innerHTML = '';
    document.getElementById('liveFeed').src = '';

    // 提交到YOLO服务
    try {
        const response = await fetch(`${YOLO_SERVER}/api/upload`, {
            method: 'POST',
            body: formData
        });
        if (response.ok) {
            // 隐藏加载动画
            loadingSpinner.style.display = 'none';

            // 启动视频流显示
            document.getElementById('liveFeed').src = `${YOLO_SERVER}/api/stream`;
            startResultUpdates();
        }
    } catch (error) {
        console.error('上传失败:', error);
        loadingSpinner.style.display = 'none';
        alert('视频上传失败，请重试！');
    }
});

// 定期更新检测结果
function startResultUpdates() {
    setInterval(async () => {
        try {
            const response = await fetch(`${YOLO_SERVER}/api/results`);
            const data = await response.json();
            const tbody = document.getElementById('results');
            tbody.innerHTML = data.map(item => `
                <tr>
                    <td>${item.class}</td>
                    <td>${item.confidence}</td>
                    <td>${item.coordinates.join(', ')}</td>
                </tr>
            `).join('');
        } catch (error) {
            console.error('获取结果失败:', error);
        }
    }, 1000);
}

// 暂停/恢复控制
async function togglePause() {
    isPaused = !isPaused;
    const endpoint = isPaused ? '/api/pause' : '/api/resume';
    try {
        await fetch(`${YOLO_SERVER}${endpoint}`, { method: 'POST' });
        document.getElementById('pauseBtn').textContent =
            isPaused ? '恢复检测' : '暂停检测';
    } catch (error) {
        console.error('控制请求失败:', error);
    }
}