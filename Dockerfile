# Update image to allow to run as Root/Privileged User on OpenShift
FROM sysdig/agent

RUN as root

#RUN chgrp -R 0 /usr/src
#RUN chmod -R g+rw /usr/src
#RUN find /usr/src -type d -exec chmod g+x {} +

#RUN chgrp -R 0 /opt/draios/etc
#RUN chmod -R g+rw /opt/draios/etc
#RUN find /opt/draios/etc -type d -exec chmod g+x {} +
