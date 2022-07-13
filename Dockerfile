FROM shadowpanther/neosvr-headless

USER root

RUN ["apt-get", "-y", "update"]
RUN ["apt-get", "-y", "install", "python3", "python3-pip"]

# From shadowpanther's image
USER $USER

ENV PATH=$PATH:/home/steam/.local/bin

COPY --chown=$USER:$USER . /home/steam/NeosVR-Headless-API
RUN ["pip3", "install", "-r", "/home/steam/NeosVR-Headless-API/requirements.txt"]

ENTRYPOINT ["/Scripts/setup_neosvr.sh", "/home/steam/NeosVR-Headless-API/rpc_server.py"]
