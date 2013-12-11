#!/usr/bin/env bash

set -e

basedir=$(cd $(dirname $0);pwd)
pyenv=${basedir}/venv/bin/activate
program=${basedir}/nicoalert.py
logfile=${basedir}/log/nicoalert.log
nohupfile=${basedir}/log/nohup.out
pgrep_target="python ${program}"
monitor_threshold=20
customenv=${basedir}/nicoalert.env

start() {
  if [ 0 -lt $(pgrep -f "${pgrep_target}" | wc -l) ]
  then
    echo "already started."
  else
    nohup ${program} >> ${nohupfile} 2>&1 &
  fi
}

stop() {
  pkill -f "${pgrep_target}" || true
  echo "killed." >> ${logfile}
}

oneshot() {
  ${program}
}

monitor() {
  echo $(date) monitor start

  if [ ! -e ${logfile} ]; then
    echo $(date) "log file ${logfile} does not exist."
    echo $(date) "trying to start application."
    stop
    start
  else
    last_modified=$(date -r ${logfile} +%s)
    current=$(date +%s)

    if [ $((${last_modified} + ${monitor_threshold})) -lt ${current} ]
    then
      echo $(date) "log file ${logfile} has not been updated for ${monitor_threshold} seconds."
      echo $(date) "trying to restart application."
      stop
      start
    fi
  fi

  echo $(date) monitor end
}

switch() {
  if [ $# -ne 1 ]; then
    echo "not enough arguments."
    echo "usage: ${0} switch dev|prod"
    return 1
  fi
    
  for target in nicoalert.config
  do
    rm ${target}
    ln -s ./${target}.${1} ./${target}
  done
}

cd ${basedir}
source ${pyenv}

if [ -e ${customenv} ]; then
  source ${customenv}
fi

case "${1}" in
  start)
    start
    ;;
  stop)
    stop
    ;;
  restart)
    stop
    start
    ;;
  oneshot)
    oneshot
    ;;
  monitor)
    monitor
    ;;
  switch)
    shift
    switch $*
    ;;
  *)
    echo "Usage: ${0} {start|stop|restart|oneshot|monitor|switch}"
    exit 1
esac
