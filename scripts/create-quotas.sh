#!/bin/bash

CREATED_UPDATED_TIMESTAMP='2020-09-29 10:23:54'
CPU_UUID=$(python -c "import uuid; print(uuid.uuid4())")
CREATE_RESOURCE_CPU="INSERT INTO __reana.resource (created,updated,id_,name,type_,unit,title) VALUES ('$CREATED_UPDATED_TIMESTAMP','$CREATED_UPDATED_TIMESTAMP','$CPU_UUID','cpu','cpu','milliseconds','cpu')"
GPU_UUID=$(python -c "import uuid; print(uuid.uuid4())")
CREATE_RESOURCE_GPU="INSERT INTO __reana.resource (created,updated,id_,name,type_,unit,title) VALUES ('$CREATED_UPDATED_TIMESTAMP','$CREATED_UPDATED_TIMESTAMP','$GPU_UUID','gpu','gpu','milliseconds','gpu')"
DISK_UUID=$(python -c "import uuid; print(uuid.uuid4())")
CREATE_RESOURCE_DISK="INSERT INTO __reana.resource (created,updated,id_,name,type_,unit,title) VALUES ('$CREATED_UPDATED_TIMESTAMP','$CREATED_UPDATED_TIMESTAMP','$DISK_UUID','disk','disk','bytes_','disk')"

CREATE_USER_RESOURCE_CPU="INSERT INTO __reana.user_resource (created,updated,user_id,resource_id,quota_limit,quota_used) VALUES ('$CREATED_UPDATED_TIMESTAMP','$CREATED_UPDATED_TIMESTAMP','00000000-0000-0000-0000-000000000000','$CPU_UUID',72000000,0)"
CREATE_USER_RESOURCE_GPU="INSERT INTO __reana.user_resource (created,updated,user_id,resource_id,quota_limit,quota_used) VALUES ('$CREATED_UPDATED_TIMESTAMP','$CREATED_UPDATED_TIMESTAMP','00000000-0000-0000-0000-000000000000','$GPU_UUID',36000000,0)"
CREATE_USER_RESOURCE_DISK="INSERT INTO __reana.user_resource (created,updated,user_id,resource_id,quota_limit,quota_used) VALUES ('$CREATED_UPDATED_TIMESTAMP','$CREATED_UPDATED_TIMESTAMP','00000000-0000-0000-0000-000000000000','$DISK_UUID',10000000000,0)"

for i in {"$CREATE_RESOURCE_CPU","$CREATE_RESOURCE_GPU","$CREATE_RESOURCE_DISK","$CREATE_USER_RESOURCE_CPU","$CREATE_USER_RESOURCE_GPU","$CREATE_USER_RESOURCE_DISK"}; do
    echo "Running:\n$ $i"
    kubectl exec -ti deployment/reana-db -- bash -c "psql -U reana -c \"$i\""
done
