nohup python3 depth_ratio_calc.py > logs_/depth_ratio_calc.log 2>&1 &
nohup python3 price_calc.py > logs_/price_calc.log 2>&1 &
nohup python3 universal_plot.py > logs_/universal_plot.log 2>&1 &


 #pgrep -fl python3
 #top -p $(pgrep -d',' -f python3)

#pkill -9 python3
#ps - check processes