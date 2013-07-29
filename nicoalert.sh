#!/usr/bin/env bash

basedir=$(cd $(dirname $0);pwd)
pyenv=${basedir}/venv/bin/activate
program=${basedir}/nicoalert.py
logfile=${basedir}/log/nicoalert.log
pgrep_target="python ${program}"
monitor_threshold=20
customenv=${basedir}/nicoalert.env

start() {
  if [ 0 -lt $(pgrep -f "${pgrep_target}" | wc -l) ]
  then
    echo "already started."
    RETVAL=2
  else
    # echo "will start"
    nohup ${program} >> ${logfile} 2>&1 &
    RETVAL=${?}
  fi
  return ${RETVAL}
}

stop() {
  pkill -f "${pgrep_target}"
  RETVAL=${?}
  echo "killed." >> ${logfile}
  return ${RETVAL}
}

oneshot() {
  ${program}
  return $?
}

monitor() {
  echo $(date) monitor start

  last_modified=$(date -r ${logfile} +%s)
  # last_modified=0
  current=$(date +%s)
  # echo $last_modified
  # echo $current

  if [ $((${last_modified} + ${monitor_threshold})) -lt ${current} ]
  then
    echo $(date) "it seems that the file ${logfile} is not updated in ${monitor_threshold} seconds, so try to restart."
    stop
    start
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
  
  return 0
}

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
    RETVAL=2
esac

exit ${RETVAL}

