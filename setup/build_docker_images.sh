#!/bin/bash
#
# build_docker_images.sh builds the necessary docker images for setting up the 
# spdw environment and repository, using the Dockerfile.base and Dockerfile 
# files in this directory.

function usage {
    echo "Usage: build_docker_image.sh  [--branch] [--conda_version version] [--docker_user username]"
    echo "                              [--fpath_custom_dockerfile fpath] [--gpu_build] "
    echo "                              [--rebuild_image (base|final|custom)]"
    echo ""
    echo "   --branch                            Branch to use when building, defaults to master."
    echo "   --conda_version                     Conda version for the Docker images - defaults "
    echo "                                       to 4.5.11, which is compatible with the repository "
    echo "                                       YMLs."
    echo ""
    echo "    --docker_user                      Username for the Docker images. "
    echo ""
    echo "    --fpath_custom_dockerfile fpath:   Build a custom Docker image from a provided "
    echo "                                       Dockerfile after the Dockerfile.base and "
    echo "                                       Dockerfile image builds, meant to allow for "
    echo "                                       further customization of a user's environment. "
    echo "                                       This Dockerfile must use setup/Dockerfile as "
    echo "                                       the base image."
    echo ""
    echo "    --gpu_build                        Build the base image (setup/Dockerfile.base) using "
    echo "                                       nvidia/cuda9.0-cudnn7-runtime-ubuntu16.04 as the "
    echo "                                       base image, instead of ubuntu:16.04 (the default)."
    echo ""
    echo "    --rebuild_image                    Rebuild this image and any subsequent images that "
    echo "                                       use this one as base. Useful if you know that "
    echo "                                       something inside has changed (e.g. the conda "
    echo "                                       environment) but Docker won't be able to register "
    echo "                                       that change. Valid options are (base, final, custom)."
    exit 1
}

while [ ! $# -eq 0 ]
do 
    case "$1" in
            --branch)
                BRANCH=$2
                shift 2
                ;;
            --conda_version)
                CONDA_VERSION=$2
                shift 2
                ;;
            --docker_user)
                DOCKER_USER=$2
                shift 2
                ;;
            --fpath_custom_dockerfile)
                FPATH_CUSTOM_DOCKERFILE=$2
                shift 2
                ;;
            --gpu_build)
                GPU_BUILD=true
                shift 1
                ;;
            --rebuild_image)
                REBUILD_IMAGE=$2
                shift 2
                ;;
            --help)
                usage
                shift
                ;;
    esac
done

if [ -z "$DOCKER_USER" ]; then
    echo "--docker_user flag must be specified!"
    exit 1
fi

if [ -z "$BRANCH" ]; then
    echo "--branch not specified, using the default of master."
    BRANCH=master
fi

if [ -z "$CONDA_VERSION" ]; then
    echo "--conda_version not specified, using the default of 4.5.11."
    CONDA_VERSION=4.5.11
fi

if [ ! -z "$REBUILD_IMAGE" ]; then
    if ! [[ "$REBUILD_IMAGE" =~ ^(base|final|custom)$ ]]; then
        echo "--rebuild_image option \"$REBUILD_IMAGE\" is not one of the "
        echo "accepted options (base, final, or custom). If you'd like to "
        echo "delete and remove one of the images, please specify one of "
        echo "these options."
        exit 1
    fi

    if [[ "$REBUILD_IMAGE" == "base" ]]; then
        echo "--rebuild_image equal to \"base\"... will delete any existing, "
        echo "spdw/base, spdw/final, and "
        echo "spdw/custom images to build them anew."
        DELETE_BASE=true
        DELETE_FINAL=true
        DELETE_CUSTOM=true
    elif [[ "$REBUILD_IMAGE" == "final" ]]; then
        echo "--rebuild_image equal to \"final\"... will delete any existing, "
        echo "spdw/final and spdw/custom images to build "
        echo "them anew."
        DELETE_FINAL=true
        DELETE_CUSTOM=true
    elif [[ "$REBUILD_IMAGE" == "custom" ]]; then
        echo "--rebuild_image equal to \"custom\"... will delete the "
        echo "spdw/custom image to build it anew."
        DELETE_CUSTOM=true
    fi

    BASE_IMAGE_EXISTS=$(docker images -q spdw/base)
    FINAL_IMAGE_EXISTS=$(docker images -q spdw/final)
    CUSTOM_IMAGE_EXISTS=$(docker images -q spdw/custom)

    if [[ "$DELETE_BASE" == "true" ]] && [[ ! -z $BASE_IMAGE_EXISTS ]]; then
        docker image rm spdw/base
    fi
    if [[ "$DELETE_FINAL" == "true" ]] && [[ ! -z $FINAL_IMAGE_EXISTS ]]; then
        docker image rm spdw/final
    fi
    if [[ "$DELETE_CUSTOM" == "true" ]] && [[ ! -z $CUSTOM_IMAGE_EXISTS ]]; then
        docker image rm spdw/custom
    fi
fi

BASE_IMAGE="ubuntu:16.04"
FNAME_ENVIRONMENT_YML="environment_cpu.yml"
if [[ ! -z "$GPU_BUILD" ]]; then
    BASE_IMAGE="nvidia/cuda:9.0-cudnn7-runtime-ubuntu16.04"
    FNAME_ENVIRONMENT_YML="environment_gpu.yml"
fi

echo "Creating images with docker username $DOCKER_USER and miniconda "
echo "version $CONDA_VERSION..."

docker build --build-arg user=$DOCKER_USER \
             --build-arg conda_version=$CONDA_VERSION \
             --build-arg base_image=$BASE_IMAGE \
             -t spdw/base --file ./Dockerfile.base ./

docker build --build-arg user=$DOCKER_USER \
             --build-arg branch=$BRANCH \
             --build-arg conda_version=$CONDA_VERSION \
             --build-arg fname_environment_yml=$FNAME_ENVIRONMENT_YML \
             -t spdw/final --file ./Dockerfile ./

if [ ! -z "$FPATH_CUSTOM_DOCKERFILE" ]; then
    echo "Building custom Docker image based off of "
    echo "$FPATH_CUSTOM_DOCKERFILE ..."
    docker build --build-arg user=$DOCKER_USER \
                 -t spdw/custom --file $FPATH_CUSTOM_DOCKERFILE ./
fi
