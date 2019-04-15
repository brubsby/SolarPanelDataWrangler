ARG base_image=ubuntu:16.04
FROM ${base_image}
LABEL maintainer="Sean Sall <ssall@alumni.nd.edu>"

ARG conda_version
ARG user

ENV CONDA_DIRPATH /opt/conda
ENV PATH $CONDA_DIRPATH/bin:$PATH
ENV USER_UID 1000

RUN apt-get update && apt-get install -y \
   bzip2 \
   cmake \
   g++ \
   git \
   graphviz \
   libgl1-mesa-glx \
   libhdf5-dev \
   rtorrent \
   sudo \
   tmux \
   vim \
   wget

RUN mkdir -p $CONDA_DIRPATH && \
    cd $CONDA_DIRPATH && \
    wget https://repo.continuum.io/miniconda/Miniconda3-${conda_version}-Linux-x86_64.sh && \
    chmod u+x Miniconda3-${conda_version}-Linux-x86_64.sh && \
    ./Miniconda3-${conda_version}-Linux-x86_64.sh -b -f -p $CONDA_DIRPATH && \
    conda install conda=4.6.11 && \
    conda install python=3.6.8 && \
    rm Miniconda3-${conda_version}-Linux-x86_64.sh

RUN useradd -m -s /bin/bash -N -u $USER_UID $user && \
    echo "$user:$user" | chpasswd && adduser $user sudo && \
    chown -R $user $CONDA_DIRPATH && \
    echo "$user    ALL=NOPASSWD: ALL" > /etc/sudoers.d/$user && \
    echo ". /opt/conda/etc/profile.d/conda.sh" >> /home/$user/.bashrc

WORKDIR /home/$user
USER $user
