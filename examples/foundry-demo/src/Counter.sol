// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract Counter {
    uint256 public value;
    mapping(address => uint256) public counts;

    event Increment(address indexed by, uint256 newValue, uint256 personalCount);

    function inc() external {
        value += 1;
        counts[msg.sender] += 1;
        emit Increment(msg.sender, value, counts[msg.sender]);
    }
}

