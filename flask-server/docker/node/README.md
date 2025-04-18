# 微信小程序后端服务

这是一个为微信小程序提供的后端服务，用于连接MySQL数据库并提供API接口。

## 功能特点

- 用户管理：注册、查询、更新用户信息
- 车辆管理：添加、查询、更新车辆信息
- 预约管理：创建、查询、更新预约状态
- 车辆预约管理：创建、查询、更新车辆预约信息
- 数据库连接测试：验证数据库配置是否正确

## 技术栈

- Node.js
- Express.js
- MySQL

## 安装部署

1. 安装依赖

```bash
npm install
```

2. 配置环境变量

复制 `.env.example` 文件为 `.env`，并根据实际情况修改数据库连接信息：

```bash
# 数据库配置
DB_HOST=117.72.120.52
DB_USER=HYTT
DB_PASSWORD=mysqlpasswd
DB_NAME=hytt
DB_PORT=3306

# 服务器配置
PORT=3000
```

3. 初始化数据库

在MySQL中执行 `database/init.sql` 文件中的SQL语句，创建数据库和表结构。

4. 启动服务

```bash
# 开发模式
npm run dev

# 生产模式
npm start
```

启动时，服务器会自动进行数据库连接测试并在控制台显示连接结果。

## 数据库连接测试

服务提供了以下API端点用于测试数据库连接：

- `GET /api/db-test` - 测试数据库连接是否成功
- `GET /api/db-test/vehicle-appointments` - 测试车辆预约表是否可访问
- `GET /api/db-test/tables` - 获取当前数据库中的表列表

这些API可以帮助您验证数据库配置是否正确，以及检查数据库中的表结构。

示例：
```bash
# 测试数据库连接
curl http://117.72.120.52:3000/api/db-test

# 测试车辆预约表访问
curl http://117.72.120.52:3000/api/db-test/vehicle-appointments

# 获取数据库表列表
curl http://117.72.120.52:3000/api/db-test/tables
```

## API接口

### 用户管理

- `GET /api/users` - 获取所有用户
- `GET /api/users/:id` - 获取单个用户
- `POST /api/users` - 创建新用户
- `PUT /api/users/:id` - 更新用户信息
- `DELETE /api/users/:id` - 删除用户
- `GET /api/users/openid/:openid` - 通过openid查找用户

### 车辆管理

- `GET /api/vehicles` - 获取所有车辆
- `GET /api/vehicles/:id` - 获取单个车辆
- `GET /api/vehicles/user/:userId` - 获取用户的所有车辆
- `POST /api/vehicles` - 添加新车辆
- `PUT /api/vehicles/:id` - 更新车辆信息
- `DELETE /api/vehicles/:id` - 删除车辆
- `GET /api/vehicles/plate/:plateNumber` - 通过车牌号查找车辆

### 预约管理

- `GET /api/bookings` - 获取所有预约
- `GET /api/bookings/:id` - 获取单个预约
- `GET /api/bookings/user/:userId` - 获取用户的所有预约
- `POST /api/bookings` - 创建新预约
- `PUT /api/bookings/:id/status` - 更新预约状态
- `PUT /api/bookings/:id` - 更新预约信息
- `DELETE /api/bookings/:id` - 删除预约
- `GET /api/bookings/date/:date` - 获取特定日期的所有预约

### 车辆预约管理

- `GET /api/vehicle-appointments` - 获取所有车辆预约
- `GET /api/vehicle-appointments/:id` - 获取单个车辆预约详情
- `GET /api/vehicle-appointments/phone/:phone` - 根据电话号码获取预约
- `GET /api/vehicle-appointments/license/:licensePlate` - 根据车牌号获取预约
- `GET /api/vehicle-appointments/date/:date` - 根据日期获取预约
- `POST /api/vehicle-appointments` - 创建新车辆预约
- `PUT /api/vehicle-appointments/:id/status` - 更新预约状态
- `PUT /api/vehicle-appointments/:id` - 更新预约信息
- `DELETE /api/vehicle-appointments/:id` - 删除预约

## 与微信小程序集成

在微信小程序中，推荐使用封装好的API工具，通过以下方式调用:

```javascript
// 导入API工具
const { userApi, vehicleApi, bookingApi, vehicleAppointmentApi } = require('../../utils/api');

// 获取用户信息
userApi.getUserByOpenid(app.globalData.openid)
  .then(res => {
    console.log('用户信息:', res);
  })
  .catch(error => {
    console.error('获取用户信息失败:', error);
  });

// 创建新预约
bookingApi.createBooking({
  user_id: userId,
  vehicle_id: vehicleId,
  booking_time: bookingTime,
  service_type: serviceType,
  notes: notes
})
  .then(res => {
    console.log('预约创建成功:', res);
  })
  .catch(error => {
    console.error('创建预约失败:', error);
  });

// 创建车辆预约
vehicleAppointmentApi.createAppointment({
  license_plate: '京A12345',
  vehicle_type: '轿车',
  name: '张三',
  phone: '13800138000',
  appointment_date: '2023-07-01',
  appointment_time: '10:00:00',
  purpose: '商务洽谈'
})
  .then(res => {
    console.log('车辆预约创建成功:', res);
  })
  .catch(error => {
    console.error('创建车辆预约失败:', error);
  });

// 测试数据库连接
const { dbTestApi } = require('../../utils/api');
dbTestApi.testConnection()
  .then(res => {
    if (res.success) {
      console.log('数据库连接成功:', res);
    } else {
      console.error('数据库连接失败:', res);
    }
  })
  .catch(error => {
    console.error('测试请求失败:', error);
  });
```

## 管理API基础URL

在微信小程序中，所有API的基础URL都集中在 `utils/config.js` 中管理：

```javascript
// 引入配置
const { API_BASE_URL } = require('../../utils/config');

// API基础URL
console.log('API服务器地址:', API_BASE_URL);
```

如果需要更改API服务器地址，只需修改 `utils/config.js` 文件中的 `API_BASE_URL` 常量即可。

## 安全注意事项

- 在生产环境中，请确保使用HTTPS协议
- 添加适当的身份验证和授权机制
- 不要在代码中硬编码敏感信息，使用环境变量 