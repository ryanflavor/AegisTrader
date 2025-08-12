# **Infrastructure and Deployment Integration**

## **Enhancement Deployment Strategy**

**Deployment Approach**: The entire market-service application will be packaged into a **single Docker container**. This container will be deployed to Kubernetes as a Deployment or StatefulSet, managed by the Helm charts located in the k8s/ directory. High availability for the gateway logic will be handled *within* the single service by the SingleActiveService leader election pattern。

## **Rollback Strategy**

**Rollback Method**: Standard Kubernetes and Helm rollback procedures will be used.
