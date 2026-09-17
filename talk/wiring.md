# ESP32-WROOM audio system wiring

适用模块：38 针 ESP32-WROOM、6 针 INMP441、6 针 MAX98357A、4 针 I2C SSD1306 OLED。

## ESP32 电源针脚

| ESP32 针脚 | 实际电压 | 用途 |
|---|---:|---|
| `3V3` | 3.3V | 给 INMP441 和 OLED 供电 |
| `VIN/5V` | USB 供电时约 5V | 给 MAX98357A 功放供电 |
| `GND` | 0V | 所有模块公共地 |

不要把 `VIN/5V` 接到 ESP32 的 `3V3`，也不要把 5V 接到 INMP441 或 OLED 的 VCC。

## 总接线表

### INMP441 六针 I2S 麦克风

| INMP441 针脚 | ESP32 接点 | 电压/信号 | 说明 |
|---|---:|---:|---|
| `VCC` / `VDD` | `3V3` | 3.3V | 麦克风电源，只能 3.3V |
| `GND` | `GND` | 0V | 公共地 |
| `SCK` | `GPIO26` | 3.3V I2S 时钟 | 必须连接 |
| `WS` | `GPIO25` | 3.3V I2S 声道时钟 | 必须连接 |
| `SD` | `GPIO33` | 3.3V I2S 数据 | 必须连接 |
| `L/R` | `GND` | 0V | 选择左声道 |

### MAX98357A 六针 I2S 功放

| MAX98357A 针脚 | ESP32 接点 | 电压/信号 | 说明 |
|---|---:|---:|---|
| `VIN` | `VIN/5V` | 约 5V | 功放电源，USB 供电时使用 |
| `GND` | `GND` | 0V | 必须共地 |
| `BCLK` | `GPIO18` | 3.3V I2S 时钟 | 必须连接 |
| `LRC` / `WS` | `GPIO19` | 3.3V I2S 声道时钟 | 必须连接 |
| `DIN` | `GPIO23` | 3.3V I2S 数据 | 必须连接 |
| `SD` / `SD_EN` | `GPIO27` | 0V/3.3V 控制 | 低电平静音，高电平启用 |

如果功放第六针标的是 `GAIN`，不是 `SD`、`SD_EN` 或 `SD_MODE`，不要接 GPIO27，保持 `GAIN` 原来的默认状态。代码仍可播放，但不能通过 GPIO27 控制静音。

### 扬声器

| 扬声器 | MAX98357A |
|---|---|
| 正端 `+` | `SPK+` |
| 负端 `-` | `SPK-` |

扬声器两端都是功放的差分输出，不能把 `SPK+` 或 `SPK-` 接 ESP32 GND。建议使用 4Ω 或 8Ω 扬声器。

### 四针蓝色 OLED

当前已经检测到地址 `0x3C`，按 I2C OLED 连接：

| OLED 针脚 | ESP32 接点 | 电压/信号 | 说明 |
|---|---:|---:|---|
| `VCC` | `3V3` | 3.3V | 屏幕电源 |
| `GND` | `GND` | 0V | 公共地 |
| `SCK` / `SCL` | `GPIO21` | 3.3V I2C 时钟 | 当前实测接法 |
| `SDA` | `GPIO22` | 3.3V I2C 数据 | 当前实测接法 |

## 完整接线图

```text
                         USB 供电
                            |
                    +-------v--------+
                    |  ESP32-WROOM   |
                    |                |
          3.3V ----| 3V3            |
          约 5V ---| VIN/5V         |
          0V ------| GND            |
                    |                |
 GPIO26 <----------| GPIO26         |----------> INMP441 SCK
 GPIO25 <----------| GPIO25         |----------> INMP441 WS
 GPIO33 <----------| GPIO33         |<---------- INMP441 SD
                    |                |
 GPIO18 ---------->| GPIO18         |----------> MAX98357A BCLK
 GPIO19 ---------->| GPIO19         |----------> MAX98357A LRC/WS
 GPIO23 ---------->| GPIO23         |----------> MAX98357A DIN
 GPIO27 ---------->| GPIO27         |----------> MAX98357A SD/EN
                    |                |
 GPIO21 ---------->| GPIO21         |----------> OLED SCK/SCL
 GPIO22 ---------->| GPIO22         |----------> OLED SDA
                    +-------+--------+
                            |
                            +-------------------- 公共 GND

 3V3  ---------------------> INMP441 VCC/VDD
 3V3  ---------------------> OLED VCC
 VIN/5V --------------------> MAX98357A VIN
 GND  ---------------------> INMP441 GND
 GND  ---------------------> INMP441 L/R
 GND  ---------------------> OLED GND
 GND  ---------------------> MAX98357A GND

 MAX98357A SPK+ -----------> speaker +
 MAX98357A SPK- -----------> speaker -
```

## 推荐上电顺序

1. 刷固件或上传程序时，先断开功放、扬声器、麦克风和 OLED，只保留 USB。
2. 确认 ESP32 可以通过 COM9 连接。
3. 先接 INMP441 和 OLED，确认 3.3V 电源没有接错。
4. 最后接 MAX98357A 的 VIN/5V 和扬声器。
5. 如果一接功放 COM9 就消失，立即断电，优先检查功放 VIN/GND 是否接反，以及 USB 电源是否掉压。

## 菜单程序

上传 `main.py` 和 `ssd1306.py` 后，进入串口 REPL：

```text
1 - OLED 显示测试
2 - 只录音，不启用功放
3 - 880Hz 功放测试音
4 - ABC 歌曲循环播放，Ctrl+C 停止
q - 退出并静音
```

菜单 `2` 只使用 INMP441 录音，不初始化 MAX98357A，因此测试录音时可以断开功放的 5V/VIN。最长录音 30 秒，录音会保存到 ESP32 的 `/recordings/record_YYYYMMDD_HHMMSS_mmm.wav`，再在电脑执行：

```powershell
conda run -n pyg python talk\download_recordings.py
```

电脑会将 WAV 下载到 `talk/recordings` 并转换为同名 MP3。ESP32 上没有直接进行 MP3 编码，MP3 转换在电脑完成。
