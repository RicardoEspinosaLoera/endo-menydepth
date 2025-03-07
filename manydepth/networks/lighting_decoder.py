# Copyright Niantic 2019. Patent Pending. All rights reserved.
#
# This software is licensed under the terms of the Monodepth2 licence
# which allows for non-commercial use only, the full terms of which are made
# available in the LICENSE file.
from __future__ import absolute_import, division, print_function

import numpy as np
import torch
import torch.nn as nn

from collections import OrderedDict
from layers import *


class LightingDecoder(nn.Module):
    def __init__(self, num_ch_enc, scales= range(4), num_output_channels=2, use_skips=False):
        super(LightingDecoder, self).__init__()

        self.num_output_channels = num_output_channels
        self.use_skips = use_skips
        self.upsample_mode = 'nearest'
        self.scales = scales

        self.num_ch_enc = num_ch_enc
        self.num_ch_dec = np.array([16, 32, 64, 128, 256])

        # decoder
        self.convs = OrderedDict() # 有序字典
        for i in range(4, -1, -1):
            # upconv_0
            num_ch_in = self.num_ch_enc[-1] if i == 4 else self.num_ch_dec[i + 1]
            num_ch_out = self.num_ch_dec[i]
            self.convs[("upconv", i, 0)] = ConvBlock(num_ch_in, num_ch_out)

            # upconv_1
            num_ch_in = self.num_ch_dec[i]
            if self.use_skips and i > 0:
                num_ch_in += self.num_ch_enc[i - 1]
            num_ch_out = self.num_ch_dec[i]
            self.convs[("upconv", i, 1)] = ConvBlock(num_ch_in, num_ch_out)

        for s in self.scales:
            self.convs[("lighting_conv", s)] = Conv3x3(self.num_ch_dec[s], self.num_output_channels)

        self.decoder = nn.ModuleList(list(self.convs.values()))
        #self.sigmoid = nn.Sigmoid()

    def forward(self, input_features):
        self.outputs = {}
        
        # decoder
        x = input_features[-1]
        #y = input_features[-1]
        for i in range(4, -1, -1):
            x = self.convs[("upconv", i, 0)](x)
            #y = self.convs[("upconv", i, 0)](y)
            x = [upsample(x)]
            #y = [upsample(y)]
            if self.use_skips and i > 0:
                x += [input_features[i - 1]]
            x = torch.cat(x, 1)
            #y = torch.cat(y, 1)
            x = self.convs[("upconv", i, 1)](x)
            #y = self.convs[("upconv", i, 1)](y)
            if i in self.scales:
                self.outputs[("lighting", i)] = self.convs[("lighting_conv", i)](x)
                #self.outputs[("constrast", i)] = self.convs[("lighting_conv", i)](y)
                # Split the output into C_t and B_t
                Ct = torch.relu(self.outputs[("lighting", i)][:, 0:1, :, :])  # Contrast (scale)
                Bt = torch.tanh(self.outputs[("lighting", i)][:, 1:2, :, :])  # Brightness (shift)

                # Store outputs
                self.outputs[("contrast", i)] = Ct
                self.outputs[("brightness", i)] = Bt

        return self.outputs
