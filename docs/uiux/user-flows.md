# **4.0 User Flows**

## **4.1 Flow 1: Monitor Service Health & Investigate Issues**

* **User Goal**: To quickly understand the overall health of all services and, upon discovering a problem, to swiftly drill down to diagnose the root cause.  
* **Flow Diagram**:  
  代码段  
  graph TD  
      A\[用户访问UI\<br\>进入 Dashboard\] \--\> B{发现不健康的服务实例};  
      B \--\> C\[点击不健康的实例\];  
      C \--\> D\[导航至服务详情页\];  
      D \--\> E\[查看详细指标、日志和配置\];  
      E \--\> F\[诊断问题根源\];

      subgraph "监控仪表盘 (Dashboard)"  
          A  
          B  
          C  
      end

      subgraph "服务详情页 (Service Detail)"  
          D  
          E  
          F  
      end

## **4.2 Flow 2: Manage Service Definitions (CRUD)**

* **User Goal**: For a system administrator to create, view, update, and delete service definitions to control which services are allowed to run in the system.  
* **Flow Diagram**:  
  代码段  
  graph TD  
      A\[管理员进入 “服务管理” 页面\] \--\> B\[UI 调用 GET /api/services\];  
      B \--\> C\[显示服务定义列表\];  
      C \--\> D{选择操作};  
      D \--\>|创建| E\[点击 “新建” \-\> 弹出表单\];  
      D \--\>|更新| F\[点击 “编辑” \-\> 弹出预填表单\];  
      D \--\>|删除| G\[点击 “删除” \-\> 弹出确认框\];

      E \--\> H\[填写表单 \-\> 提交\];  
      F \--\> H;  
      H \--\> I\[UI 调用 POST / PUT API\];  
      G \--\> J\[确认删除\];  
      J \--\> K\[UI 调用 DELETE API\];

      I \--\> L\[刷新服务列表\];  
      K \--\> L;  
      L \--\> C;
