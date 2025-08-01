# **5.0 Wireframes & Mockups**

## **5.1 Dashboard**

* **Purpose**: To provide a high-level, at-a-glance overview of the entire system's health.  
* **Layout**:  
  * A main header with the title AegisSDK 服务监控.  
  * A content area displaying a grid or list of ServiceInstanceCard components.  
  * Each card is clickable, linking to that instance's detail page.

## **5.2 Service Detail View**

* **Purpose**: To allow an operator to perform a deep-dive investigation into a specific service instance.  
* **Layout**:  
  * A header section displaying key identifiers: serviceName, instanceId, status, version.  
  * A tabbed interface for organization:  
    * **Performance Metrics Tab**: Contains historical trend charts for RPC Latency, Success/Error Rate, and Queue Depth.  
    * **Configuration Tab**: Displays the service's current configuration parameters in a read-only format.  
    * **Logs/Events Tab**: Displays a stream of recent logs or critical events for the instance.

## **5.3 Service Management Page**

* **Purpose**: To provide administrators with an interface to perform full CRUD operations on service definitions.  
* **Layout**:  
  * A header with the title 服务定义管理 and a \[ \+ 新建服务定义 \] button.  
  * A data table displaying a list of all existing ServiceDefinitions.  
  * Each row in the table includes "Edit" and "Delete" action buttons.  
  * Create/Edit operations occur within a modal form.  
  * Delete operations are protected by a confirmation dialog.
