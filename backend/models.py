"""
Seq2Seq ConvLSTM with Spatial Attention for weather forecasting.
PyTorch port of the Keras 3 model trained in Data-collector-pfe/ConvLstm/.

Input:  [B, 7, 7, 37, 65]     -> 7-day history, 7 channels (tmax,tmin,rh,u10,v10,z500,t850)
Output: [B, 7, 3, 37, 65]     -> 7-day forecast, 3 targets  (tmax,tmin,rh)
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional, Tuple, List


class ConvLSTMCell(nn.Module):
    """Single ConvLSTM cell — replaces Linear gates with Conv2d."""

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int,
        kernel_size: int = 3,
        bias: bool = True,
    ):
        super().__init__()
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim

        self.conv = nn.Conv2d(
            in_channels=input_dim + hidden_dim,
            out_channels=4 * hidden_dim,
            kernel_size=kernel_size,
            padding=kernel_size // 2,
            bias=bias,
        )

    def forward(
        self, x: torch.Tensor, state: Tuple[torch.Tensor, torch.Tensor]
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        h, c = state
        combined = torch.cat([x, h], dim=1)               # [B, C_in + C_h, H, W]
        gates = self.conv(combined)                        # [B, 4*C_h, H, W]
        i_gate, f_gate, g_gate, o_gate = torch.chunk(gates, 4, dim=1)

        i = torch.sigmoid(i_gate)
        f = torch.sigmoid(f_gate)
        g = torch.tanh(g_gate)
        o = torch.sigmoid(o_gate)

        c_next = f * c + i * g
        h_next = o * torch.tanh(c_next)
        return h_next, c_next


class ConvLSTM(nn.Module):
    """Multi-layer ConvLSTM with optional sequence return and final state return."""

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int,
        kernel_size: int = 3,
        num_layers: int = 1,
        bias: bool = True,
        return_sequences: bool = True,
        return_state: bool = False,
    ):
        super().__init__()
        self.return_sequences = return_sequences
        self.return_state = return_state

        cells = []
        for i in range(num_layers):
            cur_in = input_dim if i == 0 else hidden_dim
            cells.append(ConvLSTMCell(cur_in, hidden_dim, kernel_size, bias))
        self.cell_list = nn.ModuleList(cells)
        self.num_layers = num_layers
        self.hidden_dim = hidden_dim

    def forward(
        self,
        x: torch.Tensor,
        initial_state: Optional[List[Tuple[torch.Tensor, torch.Tensor]]] = None,
    ):
        """
        x: [B, T, C, H, W]

        Returns:
            if return_sequences=True & return_state=False:
                output:  [B, T, C_h, H, W]
            if return_sequences=True & return_state=True:
                (output, last_h, last_c)
            if return_sequences=False & return_state=False:
                last_h:  [B, C_h, H, W]
        """
        B, T, _, H, W = x.shape

        if initial_state is None:
            initial_state = [
                (
                    torch.zeros(B, self.hidden_dim, H, W, device=x.device),
                    torch.zeros(B, self.hidden_dim, H, W, device=x.device),
                )
                for _ in range(self.num_layers)
            ]

        layer_input = x
        all_outputs: List[torch.Tensor] = []

        for layer_idx, cell in enumerate(self.cell_list):
            h, c = initial_state[layer_idx]
            outputs_inner: List[torch.Tensor] = []

            for t in range(T):
                h, c = cell(layer_input[:, t, :, :, :], (h, c))
                outputs_inner.append(h)

            layer_output = torch.stack(outputs_inner, dim=1)   # [B, T, C_h, H, W]
            layer_input = layer_output
            all_outputs.append(layer_output)

        last_output = all_outputs[-1]
        last_state = (h, c)

        if self.return_sequences and self.return_state:
            return last_output, last_state[0], last_state[1]
        if self.return_sequences:
            return last_output
        return last_state[0]


class SpatialAttention(nn.Module):
    """Channel-wise spatial attention gate via 1x1 conv -> sigmoid."""

    def __init__(self, in_channels: int):
        super().__init__()
        self.conv = nn.Conv2d(in_channels, 1, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [B, C, H, W]
        attn = torch.sigmoid(self.conv(x))   # [B, 1, H, W]
        return x * attn


class Seq2SeqConvLSTM(nn.Module):
    """
    ConvLSTM Encoder-Decoder with spatial attention.

    Matches the Keras architecture:
      - Encoder: ConvLSTM2D(return_sequences=True, return_state=True)
      - LayerNorm on encoder sequences
      - SpatialAttention on the encoder final hidden state
      - RepeatVector (tile) to expand the attended context across output_window
      - Decoder: ConvLSTM2D(return_sequences=True) with encoder state as initial
      - LayerNorm on decoder output
      - TimeDistributed Conv2D(1x1, linear) projection head
    """

    def __init__(
        self,
        input_window: int = 7,
        output_window: int = 7,
        lat: int = 37,
        lon: int = 65,
        n_in: int = 7,
        n_out: int = 3,
        filters: int = 64, # Trained architecture used 64 filters!
        kernel_size: int = 3,
    ):
        super().__init__()
        self.input_window = input_window
        self.output_window = output_window
        self.filters = filters

        # Match the old architecture exactly: 
        # For enc_cell1, the checkpoint kernel has size [256, 71, 3, 3]
        # In ConvLSTMCell, out_channels = 4*hidden_dim (4*64=256), in_channels = input_dim + hidden_dim. 
        # So input_dim + 64 = 71 => input_dim = 7
        self.enc_cell1 = ConvLSTMCell(n_in, filters, kernel_size)
        
        # enc_cell2 checkpoint kernel size [256, 128, 3, 3] => in_channels 128. 
        # input_dim + 64 = 128 => input_dim = 64
        self.enc_cell2 = ConvLSTMCell(filters, filters, kernel_size)
        
        # dec_cell checkpoint kernel size [256, 67, 3, 3] => in_channels 67. 
        # input_dim + 64 = 67 => input_dim = 3 (this is the number of target features, n_out!)
        self.dec_cell = ConvLSTMCell(n_out, filters, kernel_size)
        
        # final_conv checkpoint kernel size [3, 64, 3, 3] => simple 3x3 conv mapping states to output
        self.final_conv = nn.Conv2d(filters, n_out, kernel_size=kernel_size, padding=kernel_size//2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: [B, input_window, n_in, H, W]

        Returns:
            [B, output_window, n_out, H, W]
        """
        B = x.shape[0]
        _, _, H, W = x.shape[1], x.shape[2], x.shape[3], x.shape[4]

        # --- Encoder ---
        # Initialize hidden states
        h1 = torch.zeros(B, self.filters, H, W, device=x.device)
        c1 = torch.zeros(B, self.filters, H, W, device=x.device)
        h2 = torch.zeros(B, self.filters, H, W, device=x.device)
        c2 = torch.zeros(B, self.filters, H, W, device=x.device)
        
        # Process input sequence
        for t in range(self.input_window):
            h1, c1 = self.enc_cell1(x[:, t], (h1, c1))
            h2, c2 = self.enc_cell2(h1, (h2, c2))
        
        # --- Decoder ---
        # Initial state for decoder uses final state from encoder
        h_dec, c_dec = h2, c2
        
        # Decoder input (start token, e.g., zeros)
        dec_in = torch.zeros(B, 3, H, W, device=x.device)  # 3 variables (tmax, tmin, rh)
        
        outputs = []
        for t in range(self.output_window):
            # Pass the previous prediction (or zeros for the first step) as input
            h_dec, c_dec = self.dec_cell(dec_in, (h_dec, c_dec))
            out_t = self.final_conv(h_dec)          # [B, n_out, H, W]
            dec_in = out_t                          # Auto-regressive decoding
            outputs.append(out_t)
            
        return torch.stack(outputs, dim=1)                      # [B, T_out, n_out, H, W]
