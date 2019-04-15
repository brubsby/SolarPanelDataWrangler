FROM spdw/base
LABEL maintainer="Sean Sall <ssall@alumni.nd.edu>"

ARG fname_environment_yml
ARG conda_version
ARG user
ARG branch

USER $user

RUN mkdir $HOME/repos && \
    cd $HOME/repos && \
    git clone https://github.com/typicalTYLER/SolarPanelDataWrangler.git && \
    git clone https://github.com/typicalTYLER/DeepSolar.git

USER root
RUN cd /opt && \
    wget http://download.osgeo.org/libspatialindex/spatialindex-src-1.8.5.tar.gz && \
    tar -xvf spatialindex-src-1.8.5.tar.gz && \
    cd spatialindex-src-1.8.5 && \
    ./configure; make; make install

USER $user
RUN cd $HOME/repos/SolarPanelDataWrangler &&\
    git checkout $branch && \
    cd $HOME/repos/SolarPanelDataWrangler/setup && \
    conda install conda=$conda_version && \
    conda env create -f $fname_environment_yml && \
    cd $HOME

RUN mkdir -p ~/.config/matplotlib && \
    echo "backend: Agg" > ~/.config/matplotlib/matplotlibrc

RUN cd $HOME/repos/DeepSolar && \
    mkdir ckpt && \
    cd ckpt && \
    wget https://s3-us-west-1.amazonaws.com/roofsolar/inception_classification.tar.gz && \
    wget https://s3-us-west-1.amazonaws.com/roofsolar/inception_segmentation.tar.gz && \
    tar xzf inception_classification.tar.gz && \
    tar xzf inception_segmentation.tar.gz
