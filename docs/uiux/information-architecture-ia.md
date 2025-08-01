# **3.0 Information Architecture (IA)**

## **3.1 Site Map**

代码段

graph TD  
    A\[Dashboard /\] \--\> B\[Service Detail View\<br\>/services/{instanceId}\]  
    A \--\> C\[Service Management\<br\>/manage\]

    subgraph "Service Management"  
        C \--\> C1\[List Service Definitions\]  
        C1 \--\> C2\[Create/Edit Service Form\]  
    end
