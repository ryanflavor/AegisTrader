# **AegisSDK Monitoring UI/UX Specification**

| Document Status | Final Version |
| :---- | :---- |
| **Version** | 1.0 |
| **Date** | 2025-07-31 |
| **Author** | Sally (BMad UX Expert) |

## **1.0 Introduction**

This document defines the user experience goals, information architecture, user flows, and visual design specifications for the AegisSDK Monitoring UI. It serves as the foundation for visual design and frontend development, ensuring a cohesive and user-centered experience.

## **2.0 Overall UX Goals & Principles**

### **2.1 Target Users**

The primary users are **technical and operations personnel** responsible for monitoring the health of a distributed trading system and managing its services. They prioritize data clarity and operational efficiency.

### **2.2 Usability Goals**

* **Clarity**: Provide a clean, professional, and information-dense interface.
* **Efficiency**: Enable users to quickly assess system health and rapidly diagnose the root cause of any issues.
* **Error Prevention**: Use confirmation dialogs for destructive actions like deleting a service definition.

### **2.3 Design Principles**

* **Clarity Over Cleverness**: Prioritize clear communication over aesthetic innovation.
* **Progressive Disclosure**: Show only what's needed, when it's needed, to avoid overwhelming the user.
* **Consistent Patterns**: Use familiar UI patterns throughout the application.
* **Immediate Feedback**: Every action should have a clear, immediate response.

## **3.0 Information Architecture (IA)**

### **3.1 Site Map**

代码段

graph TD
    A\[Dashboard /\] \--\> B\[Service Detail View\<br\>/services/{instanceId}\]
    A \--\> C\[Service Management\<br\>/manage\]

    subgraph "Service Management"
        C \--\> C1\[List Service Definitions\]
        C1 \--\> C2\[Create/Edit Service Form\]
    end

## **4.0 User Flows**

### **4.1 Flow 1: Monitor Service Health & Investigate Issues**

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

### **4.2 Flow 2: Manage Service Definitions (CRUD)**

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

## **5.0 Wireframes & Mockups**

### **5.1 Dashboard**

* **Purpose**: To provide a high-level, at-a-glance overview of the entire system's health.
* **Layout**:
  * A main header with the title AegisSDK 服务监控.
  * A content area displaying a grid or list of ServiceInstanceCard components.
  * Each card is clickable, linking to that instance's detail page.

### **5.2 Service Detail View**

* **Purpose**: To allow an operator to perform a deep-dive investigation into a specific service instance.
* **Layout**:
  * A header section displaying key identifiers: serviceName, instanceId, status, version.
  * A tabbed interface for organization:
    * **Performance Metrics Tab**: Contains historical trend charts for RPC Latency, Success/Error Rate, and Queue Depth.
    * **Configuration Tab**: Displays the service's current configuration parameters in a read-only format.
    * **Logs/Events Tab**: Displays a stream of recent logs or critical events for the instance.

### **5.3 Service Management Page**

* **Purpose**: To provide administrators with an interface to perform full CRUD operations on service definitions.
* **Layout**:
  * A header with the title 服务定义管理 and a \[ \+ 新建服务定义 \] button.
  * A data table displaying a list of all existing ServiceDefinitions.
  * Each row in the table includes "Edit" and "Delete" action buttons.
  * Create/Edit operations occur within a modal form.
  * Delete operations are protected by a confirmation dialog.

## **6.0 Component Library / Design System**

* **Design System Approach**: We will use **Shadcn/ui**, a collection of composable and customizable components built on Radix UI and Tailwind CSS, allowing for maximum design flexibility.
* **Core Business Components**:
  * **ServiceStatusBadge**: A colored badge to visually represent service status (ACTIVE, UNHEALTHY, STANDBY).
  * **ServiceInstanceCard**: A component for the dashboard to display a summary of a single service instance.
  * **MetricsChart**: A chart component for visualizing historical performance data.
  * **DefinitionForm**: A form, composed of base Shadcn inputs and buttons, for creating and editing service definitions.
  * **ConfirmDeleteDialog**: A modal used to confirm destructive actions.

## **7.0 Branding & Style Guide**

* **Goal**: To create a clean, professional theme suitable for a technical tool, without complex branding.
* **Color Palette**: The palette will consist of a neutral grayscale for text and backgrounds, a primary blue for interactive elements, and semantic colors (green for success/active, red for danger/unhealthy, gray for standby).
* **Typography**: A modern, clean sans-serif font stack (e.g., Inter or system UI fonts) will be used to ensure readability. A clear type scale will establish visual hierarchy.
* **Spacing**: A consistent 8px-based grid system will be used for all spacing and layout to ensure visual harmony.

## **8.0 Accessibility & Responsiveness**

* **Accessibility**: The application will adhere to **WCAG 2.1 Level AA** standards where feasible, ensuring support for keyboard navigation and screen readers.
* **Responsiveness**: The interface is designed primarily for desktop but will be responsive to ensure usability on tablet and mobile devices.
